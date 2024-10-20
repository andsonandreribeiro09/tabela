import dash
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
from dash import dcc, html, dash_table
import pandas as pd
import redis
import json
import os

# Conectando ao banco de dados Redis usando a URL da variável de ambiente
redis_url = os.environ.get('REDIS_URL')

r = redis.from_url(redis_url, decode_responses=True)

def get_user_data(batch_size=500):
    
    all_records = []

    try:
        # Recuperar todas as chaves que começam com 'ia_dummy:*'
        keys = list(r.scan_iter("ia_dummy:*"))
        
        # Dividir as chaves em lotes
        for i in range(0, len(keys), batch_size):
            batch_keys = keys[i:i + batch_size]
            batch_values = r.mget(batch_keys)  # Obter todos os valores em um único comando
            
            for record_json in batch_values:
                if record_json:
                    try:
                        record_data = json.loads(record_json)  # Converter o JSON para um dicionário
                        all_records.append(record_data)  # Adicionar o dicionário à lista
                    except json.JSONDecodeError as e:
                        print(f"Erro ao decodificar JSON: {e}")

    except Exception as e:
        print(f"Erro ao buscar dados do Redis: {e}")

    # Converter a lista de dicionários em um DataFrame
    return pd.DataFrame(all_records)

# Uso da função
df_data = get_user_data(batch_size=500)

# Criar uma coluna de data combinando ano e mês
df_data['Data'] = pd.to_datetime(df_data['Year'].astype(str) + '-' + df_data['Month'].astype(str) + '-01')

# Garantir que as colunas 'Box 9L', 'Year' e 'Country' sejam do tipo numérico onde aplicável
df_data['Box 9L'] = pd.to_numeric(df_data['Box 9L'], errors='coerce')
df_data.rename(columns={'Ano': 'Year'}, inplace=True)  # Alterar a coluna "Ano" para "Year"
df_data['Year'] = pd.to_numeric(df_data['Year'], errors='coerce')

# Layout da aplicação
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Layout da barra lateral
sidebar = html.Div(
    [
        dbc.Card(
            [
                html.Img(src="/static/logo.png", style={"width": "100%", "height": "auto"}),
                html.Hr(),
                dbc.Nav(
                    [
                        dbc.NavLink("Home", href="https://cravalbusiness.com/", active="exact"),
                        dbc.NavLink("Dashboard", href="http://127.0.0.1:5000/dashboard/", active="exact"),
                        dbc.NavLink("Tabela", href="/tabela", active="exact"),
                    ],
                    vertical=True,
                    pills=True,
                ),
            ],
            style={"height": "100vh", "padding": "20px", "backgroundColor": "#e0e0e0"},
        )
    ],
    style={"position": "fixed", "top": 0, "left": 0, "bottom": 0, "width": "150px", "zIndex": 1},  # Aumentei a largura para 200px
)

app.layout = html.Div([
    # Barra lateral (Sidebar)
    sidebar,
    dbc.Container(  # Use um container para evitar sobreposição
        [
            dbc.Row([  # Filtros
                dbc.Col([
                    html.Label('Filtrar por Fabricante:'),
                    dcc.Dropdown(
                        id='fabricante-dropdown',
                        options=[{'label': i, 'value': i} for i in df_data['Fabricante Produtor'].unique()],
                        multi=True,
                        placeholder="Selecione Fabricantes",
                    )
                ], width=3),
                dbc.Col([
                    html.Label('Filtrar por Ano:'),
                    dcc.Dropdown(
                        id='ano-dropdown',
                        options=[{'label': str(i), 'value': i} for i in df_data['Year'].unique()],
                        multi=True,
                        placeholder="Selecione Anos",
                    )
                ], width=3),
                dbc.Col([
                    html.Label('Filtrar por País:'),
                    dcc.Dropdown(
                        id='pais-dropdown',
                        options=[{'label': i, 'value': i} for i in df_data['Country'].unique()],
                        multi=True,
                        placeholder="Selecione Países",
                    )
                ], width=3),
                dbc.Col([
                    html.Label('Filtrar por Tipo:'),
                    dcc.Dropdown(
                        id='tipo-dropdown',
                        options=[{'label': i, 'value': i} for i in df_data['Type'].unique()],
                        multi=True,
                        placeholder="Selecione Tipos",
                    )
                ], width=3)
            ]),

            # Tabela dinâmica que será atualizada com base no filtro
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Tabela Dinâmica - Volume e Share por Tipo"),
                        dbc.CardBody([
                            dash_table.DataTable(
                                id='tabela-dinamica',
                                columns=[
                                    {'name': 'Ano', 'id': 'Year'},
                                    {'name': 'Fabricante', 'id': 'Fabricante Produtor'},
                                    {'name': 'País', 'id': 'Country'},
                                    {'name': 'Tipo', 'id': 'Type'},
                                    {'name': 'Total Volume', 'id': 'Total Volume'},
                                    {'name': 'Share (%)', 'id': 'Share (%)'}
                                ],
                                data=[],  # Inicialmente vazia
                                style_table={'height': '300px', 'overflowY': 'auto'},
                                style_cell={'textAlign': 'left', 'minWidth': '80px', 'maxWidth': '180px', 'whiteSpace': 'normal'},
                                style_data={'maxWidth': '180px', 'overflow': 'hidden', 'textOverflow': 'ellipsis'}
                            )
                        ])
                    ], style={"margin": "10px"})
                ], width=12)  # Aumentei a largura da coluna da tabela
            ])
        ],
        style={"margin-left": "200px"}  # Adicione uma margem esquerda para acomodar a barra lateral
    )
])

# Callback para atualizar a tabela com base nos filtros selecionados
@app.callback(
    Output('tabela-dinamica', 'data'),
    [Input('fabricante-dropdown', 'value'),
     Input('ano-dropdown', 'value'),
     Input('pais-dropdown', 'value'),
     Input('tipo-dropdown', 'value')]
)
def update_table(fabricantes, anos, paises, tipos):
    filtered_df = df_data.copy()

    # Filtro de fabricante
    if fabricantes:
        filtered_df = filtered_df[filtered_df['Fabricante Produtor'].isin(fabricantes)]
    
    # Filtro de ano
    if anos:
        filtered_df = filtered_df[filtered_df['Year'].isin(anos)]
        
    # Filtro de país
    if paises:
        filtered_df = filtered_df[filtered_df['Country'].isin(paises)]

    # Filtro de tipo
    if tipos:
        filtered_df = filtered_df[filtered_df['Type'].isin(tipos)]

    # Agrupar por 'Year', 'Fabricante Produtor', 'Country' e 'Type' e somar o volume de vendas após os filtros
    total_volume = filtered_df.groupby(['Year', 'Fabricante Produtor', 'Country', 'Type'])['Box 9L'].sum().reset_index()
    total_volume.rename(columns={'Box 9L': 'Total Volume'}, inplace=True)

    # Calcular a participação de mercado (0 a 100%)
    # Calcular a participação de mercado e converter para inteiro
    total_volume['Share (%)'] = ((total_volume['Total Volume'] / total_volume['Total Volume'].sum()) * 100).round().astype(int)


    return total_volume.to_dict('records')




