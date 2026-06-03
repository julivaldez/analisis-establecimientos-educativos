#Nombre del grupo = JPG
#Nombre de los integrantes = Pedro Vicente(Lu=325/24) , Julieta Valdez(Lu = 172/24) y Gaspar Urrutia(Lu=324/24)
#Descripción: Script donde se realizan las
# operaciones necesarias de limpieza, consultas y visualización para el desarrollo del TP

#%% Imports

import pandas as pd
import duckdb as dd
import matplotlib.pyplot as plt
#%% Lectura de documentos originales del TP.

# Lee el archivo Excel con los establecimientos educativos.
# Saltea las primeras 12 filas del encabezado que no contienen datos útiles.
ee = pd.read_excel("2025.04.08_padroin_oficial_establecimientos_educativos_die.xlsx", skiprows=12)

# Lee el archivo CSV de bibliotecas populares.
bp = pd.read_csv("bibliotecas-populares.csv")

# Lee el archivo Excel de población por edad y departamento.
# También salta las primeras 12 filas.
pp = pd.read_excel("padron_poblacion.xlsX", skiprows=12)

# Elimina la primera columna que está vacía.
pp = pp.iloc[:, 1:]
#%% Inconsistencias en los id de BP

# Por cada ID de departamento único en el DataFrame bp:
# Se verifica que todas las bibliotecas con ese mismo id tengan el mismo nombre de departamento.
# Si hay más de un nombre distinto asociado al mismo id, lo imprime como una inconsistencia.
for depto in bp['id_departamento'].unique():
    if not len(bp[bp['id_departamento']==depto]['departamento'].unique())==1:
        print(depto, bp[bp['id_departamento']==depto]['departamento'].unique())

#%% Métrica sobre EE

# Se seleccionan los establecimientos en los que todas las columnas de modalidad están vacías.
establecimiento_sin_modalidad = (ee[(ee['Común'].isnull()) & (ee['Especial'].isnull()) & (ee['Adultos'].isnull())])
#%% Métrica sobre BP

# Se examinan los valores únicos de la quinta y cuarta últimas columnas del DataFrame bp.
# Esta exploración permite observar posibles categorías irrelevantes.
bp.iloc[:,-5].unique()
bp.iloc[:,-4].unique()
#%% Procesamiento bp

# Procesamiento del campo mail de las bibliotecas: se extrae el dominio.
# Esta función recibe un string con un email y devuelve el dominio del correo (parte entre '@' y '.').
# Si el valor no es una cadena, devuelve None.
def parsear_mail(mail):
    if type(mail) != str:
        return None
    arroba = 0
    punto = 0
    for i in range(len(mail)):
        if mail[i] == '@':
            arroba = i
    for i in range(arroba, len(mail)):
        if mail[i] == '.':
            punto = i
            break
    return mail[arroba+1:punto]


# Se construye el DataFrame de bibliotecas populares con las columnas relevantes.
bibliotecas_populares = bp[['id_departamento', 'departamento',
                            'mail', 'fecha_fundacion']].rename(columns={'mail': 'dominio_correo'})

# Correcciones de formato
bibliotecas_populares['id_departamento'] = bibliotecas_populares['id_departamento'].astype('str')
bibliotecas_populares.loc[:, 'dominio_correo'] = bibliotecas_populares.loc[:, 'dominio_correo'].apply(parsear_mail)
bibliotecas_populares['id'] = bibliotecas_populares.index # Creamos el id (Usar id original??)
bibliotecas_populares['anio_fundacion'] = bibliotecas_populares['fecha_fundacion'].str[:4].astype('Int64')
bibliotecas_populares = bibliotecas_populares.drop('fecha_fundacion', axis=1) # Eliminamos la columna original 'fecha_fundacion'
#%% Construcción de la tabla provincias

# Se seleccionan y renombran columnas de la tabla original.
provincia = bp.loc[:, ['id_provincia', 'provincia']].drop_duplicates(subset='id_provincia').sort_values('id_provincia').rename(columns={'provincia': 'nombre'})
provincia['id_provincia'] = provincia['id_provincia'].astype('str')

#%% Construcción de la tabla niveles
niveles_dict = {'id_nivel': [0, 1, 2], 'nivel': ['jardin', 'primaria', 'secundaria']}

niveles = pd.DataFrame(niveles_dict)
#%% Procesamiento de EE

# Filtramos columnas y filas según la modalidad “Común”.
establecimientos_educativos = pd.concat([ee[['Código de departamento', 'Departamento', 'Cueanexo']], ee.loc[:, 'Común':'Secundario - INET']], axis=1)
establecimientos_educativos = establecimientos_educativos[establecimientos_educativos['Común']==1].drop(columns=['Común'])

# Se eliminan filas sin ningún nivel educativo.
establecimientos_educativos = establecimientos_educativos.drop(establecimientos_educativos[establecimientos_educativos.loc[:, 'Nivel inicial - Jardín de infantes':'Secundario - INET'].sum(axis=1)==0].index)
#%% Construcción de niveles_x_establecimiento

# Devuelve los CUEANEXO de establecimientos
# que tengan al menos uno de los niveles indicados.
def obtener_niveles_x_establecimiento(niveles):
    res = establecimientos_educativos[establecimientos_educativos[niveles[0]]==1]['Cueanexo'].copy()
    for nivel in niveles[1:]:
        new = establecimientos_educativos[establecimientos_educativos[nivel]==1]['Cueanexo'].copy()
        pd.concat([res, new], axis=0)
    return pd.DataFrame(res).drop_duplicates()

# Para cada nivel educativo, se obtienen los IDs de 
# los establecimientos y se les asigna el código de nivel.
jardin = obtener_niveles_x_establecimiento(['Nivel inicial - Jardín de infantes'])
jardin['nivel'] = 0

primario = obtener_niveles_x_establecimiento(['Primario'])
primario['nivel'] = 1

secundario = obtener_niveles_x_establecimiento(['Secundario', 'Secundario - INET'])
secundario['nivel'] = 2

# Se concatenan todos los niveles en un solo DataFrame.
niveles_x_establecimiento = pd.concat([jardin, primario, secundario], axis = 0)
#%% ee
establecimientos_educativos = establecimientos_educativos.iloc[:, 0:3]
establecimientos_educativos = establecimientos_educativos.rename(columns={'Código de departamento': 'id_departamento'})
#%% Construcción de poblaciones_x_depto
# Extracción de departamentos del archivo de población (aquellos que empiezan con AREA).
pp_deptos = pp[pp['Unnamed: 1'].str.startswith('AREA', na=False)].iloc[:,0:2]
pp_deptos = pp_deptos.rename(columns={'Unnamed: 1': 'id_departamento','Unnamed: 2': 'nombre'})
deptos_index = pp_deptos.index

# Construcción del diccionario con las poblaciones por grupo etario.
poblacion_por_nivel = {'jardin': [], 'primaria':[], 'secundaria':[], 'total':[]}

# Recorre cada departamento para sumar su población por grupos de edad.
for i in range(len(deptos_index)-1):
    edades = pp.iloc[deptos_index[i]+3:deptos_index[i+1]-1, :2]
    poblacion_por_nivel['total'].append(edades.iloc[-1,-1])
    edades = edades.iloc[:-1, :]
    jardin = edades[(edades.iloc[:, 0] >= 1) & (edades.iloc[:, 0] <= 5)].iloc[:, 1].sum()
    primaria = edades[(edades.iloc[:, 0] >= 6) & (edades.iloc[:, 0] <= 12)].iloc[:, 1].sum()
    secundaria = edades[(edades.iloc[:, 0] >= 13) & (edades.iloc[:, 0] <= 18)].iloc[:, 1].sum()
    poblacion_por_nivel['jardin'].append(jardin)
    poblacion_por_nivel['primaria'].append(primaria)
    poblacion_por_nivel['secundaria'].append(secundaria)

# Se repite para el último departamento.
edades = pp.iloc[deptos_index[-1] + 3:56583, :2]
poblacion_por_nivel['total'].append(edades.iloc[-1,-1])
edades = edades.iloc[:-1, :]
jardin = edades[(edades.iloc[:, 0] >= 1) & (edades.iloc[:, 0] <= 5)].iloc[:, 1].sum()
primaria = edades[(edades.iloc[:, 0] >= 6) & (edades.iloc[:, 0] <= 12)].iloc[:, 1].sum()
secundaria = edades[(edades.iloc[:, 0] >= 13) & (edades.iloc[:, 0] <= 18)].iloc[:, 1].sum()
poblacion_por_nivel['jardin'].append(jardin)
poblacion_por_nivel['primaria'].append(primaria)
poblacion_por_nivel['secundaria'].append(secundaria)

#%% Corrección del id_departamento para comunas

# Se resetea el índice y se normaliza el formato del id_departamento (últimos 5 dígitos, sin ceros a la izquierda)
departamento = pp_deptos.reset_index(drop=True)
departamento.loc[:, 'id_departamento'] = departamento.loc[:, 'id_departamento'].str[-5:]
departamento['id_departamento'] = departamento['id_departamento'].str.lstrip('0').astype('int64')


# Consulta SQL para corregir la asociación entre comunas y departamentos en CABA.
# Se unen los departamentos con EE, y se conservan los que coincidan por nombre (para comunas) ,
# o que no sean comunas explícitamente.
consultaDepSQL = """SELECT d.nombre, e.id_departamento
                    FROM departamento AS d, establecimientos_educativos AS e
                    WHERE d.nombre 
                    LIKE 'Comuna%' AND d.nombre = e.Departamento
                    UNION
                    SELECT d.nombre, d.id_departamento FROM departamento AS d 
                    WHERE d.nombre NOT LIKE 'Comuna %'
                    ORDER BY e.id_departamento
"""

departamento = dd.query(consultaDepSQL).df()
departamento = departamento.astype({'id_departamento': 'str'})

# Se normaliza el nombre del departamento (saca acentos) y se crea id_provincia a partir del id_departamento
departamento.loc[:, 'nombre'] = departamento.loc[:, 'nombre'].str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
departamento.loc[:, 'id_provincia'] = departamento.loc[:, 'id_departamento'].str[:-3]

# Se construye el DataFrame poblaciones_x_depto combinando el id_departamento con las poblaciones por nivel
departamento = pd.concat([departamento, pd.DataFrame(poblacion_por_nivel)], axis=1)


# Se agrega la fila especial para CABA
departamento.loc[len(departamento)] = ['CABA', '2000', '2', 0, 0, 0, 0]
departamento.loc[len(departamento)-1, 'jardin':] = departamento[departamento['id_departamento'].str.contains('^2...$', regex=True)].loc[:, 'jardin':].sum()

#%% Correcciones específicas para Tierra Del Fuego
departamento.loc[len(departamento)] = ['Antártida Argentina', '94028', '94', 0, 0, 0, 0]
departamento.loc[departamento['nombre']=='Ushuaia', :'id_provincia'] = ['Ushuaia', '94014', '94']
departamento.loc[departamento['nombre']=='Rio Grande', :'id_provincia'] = ['Rio Grande', '94007', '94']
#%% Verificar inconsistencias entre nombres de departamentos en BP y en tabla de departamentos
consultaSQL = """
                SELECT b.departamento, b.id_departamento, d.id_departamento, d.nombre
                FROM bibliotecas_populares AS b
                JOIN departamento AS d
                ON b.id_departamento == d.id_departamento
                WHERE LOWER(d.nombre) != LOWER(b.departamento)
                ORDER BY d.id_departamento
"""
consulta1 = dd.query(consultaSQL).df()

bibliotecas_populares[bibliotecas_populares['id_departamento']=='82119']

# Consulta para verificar inconsistencias de nombres en EE vs Departamento
consultaSQL = """
                SELECT e.Departamento, e.id_departamento, d.id_departamento, d.nombre
                FROM establecimientos_educativos AS e
                JOIN departamento AS d
                ON e.id_departamento == d.id_departamento
                WHERE LOWER(d.nombre) != LOWER(e.departamento)
                ORDER BY d.id_departamento
"""
consulta2 = dd.query(consultaSQL).df()
#%% CONSULTAS SQL – Reportes del análisis del trabajo práctico

# Consulta 1 – Relación entre EE y población por nivel, agrupado por departamento y provincia
consultaSQL = """SELECT p.nombre AS Provincia, d.nombre AS Departamento,
                        COUNT(CASE WHEN nxe.nivel=0 THEN 1 END) AS Jardines,
                        d.jardin AS 'Población Jardín',
                        COUNT(CASE WHEN nxe.nivel=1 THEN 1 END) AS Primarias,
                        d.primaria AS 'Población Primaria',
                        COUNT(CASE WHEN nxe.nivel=2 THEN 1 END) AS Secundarios,
                        d.secundaria AS 'Población Secundaria'
                        FROM departamento AS d
                        JOIN provincia AS p ON d.id_provincia = p.id_provincia
                        LEFT JOIN establecimientos_educativos AS e ON d.id_departamento = e.id_departamento
                        LEFT JOIN niveles_x_establecimiento AS nxe ON nxe.Cueanexo = e.Cueanexo
                        WHERE d.id_departamento != '2000'
                        GROUP BY d.nombre, p.nombre, jardin, primaria, secundaria
                        ORDER BY p.nombre, Primarias DESC
"""
depto_x_grupo_etario = dd.query(consultaSQL).df()
#%% Consulta 2 – Cantidad de BP fundadas desde 1950 por departamento
consultaSQL = """
                SELECT p.nombre AS Provincia, d.nombre AS Departamento,
                COUNT(CASE WHEN bib.anio_fundacion >= 1950 THEN 1 END) AS 'Cantidad de BP fundadas desde 1950'
                FROM departamento AS d 
                JOIN provincia AS p ON d.id_provincia = p.id_provincia
                LEFT JOIN bibliotecas_populares AS bib ON bib.id_departamento = d.id_departamento
                WHERE d.nombre NOT LIKE 'Comuna%'
                GROUP BY d.nombre, p.nombre
                ORDER BY p.nombre, COUNT(CASE WHEN bib.anio_fundacion >= 1950 THEN 1 END) DESC
"""
bibliotecas_desde_1950 = dd.query(consultaSQL).df()
#%%

# Consulta 3 – Cantidad de EE, BP y población total por departamento
consultaCABA = """
                SELECT 'Ciudad Autónoma de Buenos Aires' AS Provincia, 'CABA' AS Departamento, 
                SUM(sub.Cant_EE) AS Cant_EE,
                SUM(sub.Cant_BP) AS Cant_BP,
                SUM(sub.Población) AS Población
                FROM
                (SELECT p.nombre AS Provincia, d.nombre AS Departamento,
                COUNT(DISTINCT e.Cueanexo) AS Cant_EE,
                COUNT(DISTINCT bib.id) AS Cant_BP,
                d.total AS Población
                FROM departamento AS d
                JOIN provincia AS p ON p.id_provincia = d.id_provincia
                LEFT JOIN bibliotecas_populares AS bib ON d.id_departamento = bib.id_departamento
                LEFT JOIN establecimientos_educativos AS e ON d.id_departamento = e.id_departamento
                WHERE d.id_departamento LIKE '2___'
                GROUP BY d.nombre, p.nombre, d.total) sub """
               
consultaRestoPaís = """UNION
                SELECT p.nombre AS Provincia, d.nombre AS Departamento,
                COUNT(DISTINCT e.Cueanexo) AS Cant_EE,
                COUNT(DISTINCT bib.id) AS Cant_BP,
                d.total AS Población
                FROM departamento AS d
                JOIN provincia AS p ON p.id_provincia = d.id_provincia
                LEFT JOIN bibliotecas_populares AS bib ON d.id_departamento = bib.id_departamento
                LEFT JOIN establecimientos_educativos AS e ON d.id_departamento = e.id_departamento
                WHERE d.id_departamento NOT LIKE '2___'
                GROUP BY d.nombre, p.nombre, d.total
                ORDER BY Cant_EE DESC, Cant_BP DESC, p.nombre ASC, d.nombre ASC """

ee_bp_x_depto = dd.query(consultaCABA + consultaRestoPaís).df()
#%% Consulta 4 – Dominio de correo más común por departamento
consultaSQL = """
                SELECT p.nombre AS Provincia, d.nombre AS Departamento, 
                c.dominio_correo AS 'Dominio más frecuente en BP'
                FROM departamento AS d
                JOIN provincia AS p ON d.id_provincia = p.id_provincia
                JOIN (
                    SELECT bib.dominio_correo, bib.id_departamento AS departamento,
                    COUNT(DISTINCT bib.id) AS Bibliotecas
                    FROM bibliotecas_populares AS bib
                    WHERE bib.dominio_correo != 'None' AND bib.id_departamento = d.id_departamento
                    GROUP BY bib.dominio_correo, id_departamento
                    ORDER BY Bibliotecas DESC
                    LIMIT 1 ) c ON c.departamento = d.id_departamento
                GROUP BY d.nombre, p.nombre, dominio_correo
                ORDER BY p.nombre
"""
correos_bp_x_depto = dd.query(consultaSQL).df()
#%%

# VISUALIZACIONES – Parte gráfica del trabajo
departamento['id_departamento'] = departamento['id_departamento'].astype('int64')
bibliotecas_populares['id_departamento'] = bibliotecas_populares['id_departamento'].astype('int64')

# Gráfico de cantidad de BP por provincia
bp_con_provincia = bibliotecas_populares.merge(departamento, on='id_departamento').merge(provincia, on='id_provincia')
bp_con_provincia = bp_con_provincia[['id', 'nombre_y']].rename(columns={'nombre_y': 'provincia', 'id': 'bibliotecas'})
bps_x_provincia = bp_con_provincia.groupby(['provincia']).count().sort_values('bibliotecas', ascending=True)
plt.barh(bps_x_provincia.index, bps_x_provincia['bibliotecas'])
#%%
# Gráfico de cantidad de EE por población y grupo etario
jardin = depto_x_grupo_etario[['Departamento', 'Jardines', 'Población Jardín']].sort_values('Población Jardín')
primaria = depto_x_grupo_etario[['Departamento', 'Primarias', 'Población Primaria']].sort_values('Población Primaria')
secundaria = depto_x_grupo_etario[['Departamento', 'Secundarios', 'Población Secundaria']].sort_values('Población Secundaria')

plt.scatter(jardin['Población Jardín'], jardin['Jardines'], label='Jardin', c='green', alpha=0.5)
plt.scatter(primaria['Población Primaria'], primaria['Primarias'], label='Primaria', c='yellow', alpha=0.4)
plt.scatter(secundaria['Población Secundaria'], secundaria['Secundarios'], label='Secundaria', c='red', alpha=0.3)

# Oculta los ticks del eje X para no saturar
plt.legend()
plt.show()
#%% Boxplot de EE por provincia, ordenado por mediana

establecimientos_educativos.loc[:, 'id_departamento'] = establecimientos_educativos['id_departamento'].astype('int64')

# Contamos la cantidad de establecimientos en cada departamento
cant_ee_x_depto = (establecimientos_educativos[['id_departamento', 'Cueanexo']]
                   .groupby(['id_departamento']).count().rename(columns={'Cueanexo':'Cant_EE'}))

# Indicamos la provincia y agregamos sus nombres
ee_x_depto_prov = cant_ee_x_depto.merge(departamento[['id_departamento', 'id_provincia']], on='id_departamento')
ee_box = ee_x_depto_prov.merge(provincia, on='id_provincia')

# Calculamos la mediana de cada provincia y las ordenamos
provincias_x_mediana = ee_box.groupby(['nombre'])['Cant_EE'].median().rename("Mediana").sort_values(ascending=False)

# Hacemos el boxplot
fig, ax = plt.subplots(figsize=(15,10))

# Agrupamos los datos por provincias
box = [ee_box[ee_box['nombre']==prov]['Cant_EE'] for prov in provincias_x_mediana.index]

ax.boxplot(box, 
           tick_labels=provincias_x_mediana
           .rename(index={'Ciudad Autónoma de Buenos Aires':'CABA',
                          'Santiago del Estero': 'Sgo. Estero', 'Tierra del Fuego': 'TDF'}).index, 
           showfliers=True, showmeans=True)

ax.tick_params('x', rotation=90)


fig.suptitle('')
ax.set_title('Establecimientos Educativos')
ax.set_xlabel('Provincia')
plt.savefig('Boxplot provincias')
plt.show()
#%%
# Relación entre EE y BP cada 1000 habitantes
ee_bp_cadaMil = ee_bp_x_depto[['Departamento', 'Cant_EE', 'Cant_BP', 'Población']]
ee_bp_cadaMil['Cant_EE_cadaMil'] = (1000 * ee_bp_cadaMil['Cant_EE']) / ee_bp_cadaMil['Población']
ee_bp_cadaMil['Cant_BP_cadaMil'] = (1000 * ee_bp_cadaMil['Cant_BP']) / ee_bp_cadaMil['Población']
ee_bp_cadaMil = ee_bp_cadaMil.drop(columns=['Cant_EE','Cant_BP','Población'])
ee_bp_cadaMil = ee_bp_cadaMil.dropna(subset=['Cant_EE_cadaMil', 'Cant_BP_cadaMil'])
plt.scatter(ee_bp_cadaMil['Cant_EE_cadaMil'], ee_bp_cadaMil['Cant_BP_cadaMil'], alpha=0.5)
plt.xlabel('EE cada 1000 habitantes')
plt.ylabel('BP cada 1000 habitantes')
plt.title('Relación entre EE y BP cada 1000 habitantes por departamento')
plt.show()
