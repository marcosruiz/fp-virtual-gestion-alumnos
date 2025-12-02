#Import the modules
import json
import time
import random
import subprocess
import os
import sys
import io
import smtplib
import ssl
import traceback
from datetime import datetime
from Config import *
from Conexion import *
from classes.Alumno import *
from classes.Centro import *
from classes.Ciclo import *
from classes.Modulo import *
from email.message import EmailMessage
from email.headerregistry import Address
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
import re

filename_md = "";
filename_csv = "";

def main():

    # Preparo el fichero log para escribir en él.
    global filename_md
    print("Comenzamos con el fichero")
    datetimeForFilename = get_date_time_for_filename()
    print("filename: " + datetimeForFilename)
    filename_md = "/var/fp-distancia-gestion-usuarios-automatica/logs/" + SUBDOMAIN + "/html/" + datetimeForFilename + SUBDOMAIN + ".md"
    print("filename_md: " + filename_md)

    ## Preparao el fichero csv para escribir en él.
    global filename_csv
    filename_csv = "/var/fp-distancia-gestion-usuarios-automatica/csvs/" + datetimeForFilename + SUBDOMAIN + ".csv"
    print("filename_csv: " + filename_csv)
    
    #
    escribeEnFichero(filename_md, "# Informe de gestion alumnos\n")
    escribeEnFichero(filename_md, get_date_time_for_humans())
    escribeEnFichero(filename_md, "\n## ENTORNO\n")
    escribeEnFichero(filename_md, SUBDOMAIN)
    escribeEnFichero(filename_md, "\n## RESUMEN DETALLADO\n")
    # ids de users creados en deploy que no hay que borrar
    usuarios_moodle_no_borrables = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 3725, 3729, 3730, 7152, 7490, 7491, 11720, 12270, 12272]
    # 
    moodle = get_moodle(SUBDOMAIN)[0]
    alumnos_sigad = []
    alumnos_moodle = get_alumnos_moodle_no_borrados(moodle) # Alumnos que figuran en moodle antes de ejecutar el script
    # contadores
    num_alumnos_pre_app = 0
    num_alumnos_post_script = 0
    num_alumnos_suspendidos = 0
    num_alumnos_reactivados = 0
    num_alumnos_modificado_login = 0
    num_alumnos_modificado_email = 0
    num_alumnos_creados = 0
    num_alumnos_no_creables = 0
    num_modulos_matriculados = 0
    num_matriculas_suspendidas = 0
    num_matriculas_reactivadas = 0
    num_matriculas_borradas = 0
    num_alumnos_no_matriculados_en_cursos_inexistentes = 0
    num_emails_enviados = 0
    num_emails_no_enviados = 0
    num_tutorias_suspendidas = 0
    #
    num_alumnos_pre_app = len(alumnos_moodle)

    #########################################
    # Obtengo curso académico que debo usar
    #########################################
    curso_academico = get_curso_para_REST()
    
    #########################################
    # Cuando se actualiza en el entorno pre o www se realiza la consulta al WebService de SIGAD
    # --
    # Transformo JSON de SIGAD a lista
    #########################################

    procesa_desde_fichero = False # Procesa desde fichero en lugar del ws
    if procesa_desde_fichero:
        with open(PATH + "jsons/20250925_01.json", "r", encoding="utf-8") as f:
            y = json.load(f)
        if y is not None:
            codigo=y["codigo"]
            mensaje=y["mensaje"]
            print("codigo: " + str(codigo) + ", mensaje: " + str(mensaje))
            procesaJsonEstudiantes(y, alumnos_sigad)
    else: 
        # Creo la conexión para la 1era llamada
        conexion_1er_ws = Conexion(url1, path1 + curso_academico, usuario1, password1, method1)
        # Hago la 1era llamada
        print( 'Making the call to the 1st web service:')
        resp_data = conexion_1er_ws.getJson()
        y = json.loads(resp_data)
        if y is not None:
            codigo=y["codigo"]
            mensaje=y["mensaje"]
            idSolicitud=y["idSolicitud"]
            print("Código: " , codigo, ", Mensaje: ", mensaje, "idSolicitud: ", idSolicitud)
            guarda_fichero_respuesta_ws1(get_date_time() + "." + SUBDOMAIN + ".ws1.json", resp_data)
            if codigo == 0: # éxito en la 1era llamada
                # 
                print( 'Waiting 10 seconds before the first call to the 2nd web service...')
                for x in range(1, 11):
                    time.sleep( 10 )
                    print( 'Iteration number ' + str(x))
                    conexion_2ndo_ws = Conexion(url2, path2 + str(idSolicitud), usuario2, password2, method2)
                    resp_data = conexion_2ndo_ws.getJson()
                    y = json.loads(resp_data)

                    if y is not None:
                        codigo=y["codigo"]
                        mensaje=y["mensaje"]
                        print("codigo: " + str(codigo) + ", mensaje: " + str(mensaje))
                        if codigo == 0: # éxito de la 2nda llamada
                            guarda_fichero_respuesta_ws2(get_date_time() + "." + SUBDOMAIN + ".ws2.json", resp_data )
                            procesaJsonEstudiantes(y, alumnos_sigad)
                            break
                        else: # Error  en la 2ª llamada
                            print("Fichero aún no listo. Código: " + str(codigo) 
                                + ", mensaje: " + str(mensaje))
            else: # Error en la 1era llamada
                print("Error en la llamada al 1er web service")

    

    ########################
    # Obtengo los alumnos (profesores no) que están suspendidos en moodle y miro si están en el fichero de SIGAD
    # Si están en el fichero de SIGAD los reactivo
    ########################
    escribeEnFichero(filename_md, "\n### Estudiantes suspendidos en Moodle pero que están en el fichero de SIGAD (habria que reactivar):\n")
    
    escribeEnFichero(filename_md, get_date_time_for_humans())
    
    alumnos_suspendidos = get_alumnos_suspendidos(moodle)
    for alumnoMoodle in alumnos_suspendidos:
        # comprobamos si existe por dni/nie/...
        for alumnoSIGAD in alumnos_sigad:
            if alumnoMoodle['username'] is not None \
                    and alumnoSIGAD.getDocumento() is not None \
                    and alumnoMoodle['username'].lower() == alumnoSIGAD.getDocumento().lower():
                reactiva_usuario( moodle, alumnoMoodle['userid'] )
                escribeEnFichero(filename_md, "- Estudiante '"+ alumnoMoodle['userid']+ "' reactivado" )
                matricula_alumno_en_cohorte_alumnado(moodle, alumnoMoodle['userid'] )
                num_alumnos_reactivados = num_alumnos_reactivados + 1
                break
    
    ########################
    # Localizo los alumnos (los profesores no) que estén en moodle y no en SIGAD (en base a su dni/nie/...)
    # también aprovecho para actualizar emails se procede
    ########################
    print("## Localizo los alumnos que estén en moodle y no en SIGAD y también aprovecho para actualizar emails se procede:")
    escribeEnFichero(filename_md, "\n### Alumnos a los que estando en SIGAD y Moodle se les ha actualizado el email:\n")
    escribeEnFichero(filename_md, get_date_time_for_humans() + "\n")
    alumnos_en_moodle_pero_no_SIGAD = [  ]
    for alumnoMoodle in alumnos_moodle:
        existe = False
        # comprobamos si existe por dni/nie/...
        for alumnoSIGAD in alumnos_sigad:
            if alumnoSIGAD.getDocumento() is None:
                continue
                
            if alumnoMoodle['username'].lower().strip() == alumnoSIGAD.getDocumento().lower().strip():
                existe = True
                # Si el usuario está en Moodle y en SIGAD miro si en SIGAD sigue teniendo el mismo email
                # si no coinciden el email en SIGAD y en Moodle entonces actualizo en Moodle al email que haya en SIGAD
                print("alumnoSIGAD.getEmailSigad(): ", alumnoSIGAD.getEmailSigad())
                print("alumnoMoodle['email']: ", alumnoMoodle['email_sigad'])
                if alumnoSIGAD.getEmailSigad() is not None and alumnoMoodle['email_sigad'] is not None and alumnoSIGAD.getEmailSigad().lower() != alumnoMoodle['email_sigad'].lower():
                    userid = alumnoMoodle['userid']
                    email_nuevo = alumnoSIGAD.getEmailSigad().lower()
                    update_moodle_email_sigad(userid, email_nuevo)
                    num_alumnos_modificado_email = num_alumnos_modificado_email + 1
                    escribeEnFichero(filename_md, "- Al alumno " + alumnoMoodle['username'] + " que tenia el email " + alumnoMoodle['email'] + \
                        " se le ha cambiado a " + alumnoSIGAD.getEmailSigad() + ").")
                #
                break
        
        if not existe:
            alumnos_en_moodle_pero_no_SIGAD.append(alumnoMoodle)
            
    print("## Alumnos que estan en moodle y no en SIGAD")
    escribeEnFichero(filename_md, "### (" + get_date_time_for_humans() + ") Alumnos que estan en moodle y no en SIGAD:\n")
    for alumnoMoodle in alumnos_en_moodle_pero_no_SIGAD:
        print("alumnoMoodle: ", alumnoMoodle)
        escribeEnFichero(filename_md, "- alumnoMoodle: " + str(alumnoMoodle) )
    
    ########################
    # De cada alumno que esté en moodle y no en sigad miro si en moodle hay alguien con ese email
    # - si hay alguien con ese email considero que es la misma persona a la que han actualizado de NIE a DNI en SIGAD y la actualizo
    # TODO: Utilizar este bucle como ejemplo para las que su nombre ha cambiado
    # - si no hay nadie con ese email considero que es una baja y lo suspendo
    ########################
    print("## Alumnos que habría que actualizar su id:")
    escribeEnFichero(filename_md, "\n### Alumnos a los que se ha actualizado su login\n")
    escribeEnFichero(filename_md, get_date_time_for_humans() + "\n")
    alumnos_a_suspender = [ ] # los que no haya que actualizar son para suspender, irán aquí
    for alumnoMoodle in alumnos_en_moodle_pero_no_SIGAD:
        existe = False
        # comprobamos si existe por email
        for alumnoSIGAD in alumnos_sigad:
            # Si el alumno ha pasado de un NIE a un DNI en SIGAD se lo actualizo el usuario en moodle
            if alumnoSIGAD.getEmailSigad() is not None \
                    and alumnoSIGAD.getDocumento() is not None \
                    and es_nie_valido(alumnoMoodle['username']) \
                    and es_dni_valido(alumnoSIGAD.getDocumento()) \
                    and alumnoMoodle['email_sigad'].lower() == alumnoSIGAD.getEmailSigad().lower(): 
                existe = True
                print("Alumno a actualizar su login por coincidencia de email: '", repr(alumnoMoodle),"'", sep="" )
                print("habría que ponerle de login '", alumnoSIGAD.getDocumento(),"'", sep="" )
                userid = alumnoMoodle['userid']
                username_nuevo = alumnoSIGAD.getDocumento().lower().strip()
                update_moodle_username(moodle, userid, username_nuevo)
                num_alumnos_modificado_login = num_alumnos_modificado_login + 1
                escribeEnFichero(filename_md, "- Al alumno que tenia usuario de acceso " + alumnoMoodle['username'] + \
                        " se le ha cambiado a " + alumnoSIGAD.getDocumento() + \
                        "(" + alumnoSIGAD.getEmailSigad().lower() + ").")
                # Le envío email avisándolede su cambio de usuario 
                usuario = alumnoSIGAD.getDocumento()
                oldUsuario = alumnoMoodle['username']

                plantilla_path = Path("/var/fp-distancia-gestion-usuarios-automatica/templates/nombreUsuarioActualizado.html")
                plantilla = plantilla_path.read_text(encoding="utf-8")

                mensaje = plantilla.format(
                    subdomain = SUBDOMAIN,
                    usuario = usuario,
                    oldUsuario = oldUsuario,
                )
                
                destinatario = "gestion@fpvirtualaragon.es"
                if SUBDOMAIN == "www":
                    destinatario = alumnoSIGAD.getEmailDominio().lower() 
                else:
                    print("Debería haberse enviado a '", alumnoSIGAD.getEmailDominio().lower(), "'.", sep="" )

                enviado = send_email( destinatario , "FP virtual - Aragón", mensaje)

                if enviado:
                    num_emails_enviados = num_emails_enviados + 1
                    print("num_emails_enviados: ", num_emails_enviados)
                else:
                    num_emails_no_enviados = num_emails_no_enviados + 1
                    print("Ha fallado el envío del email a'", destinatario, "'. Total fallos: '", num_emails_no_enviados, "'")

                break
        if not existe:
            alumnos_a_suspender.append(alumnoMoodle)

    
    print("## Alumnos a suspender totalmente de Moodle")
    escribeEnFichero(filename_md, "\n### Estudiantes a suspender totalmente de Moodle al no estar en SIGAD, 1ero matrículas y 2ndo a ellos:\n")
    escribeEnFichero(filename_md, get_date_time_for_humans() + "\n")
    for alumnoMoodle in alumnos_a_suspender:
        print("- ", repr(alumnoMoodle) )
        if int(alumnoMoodle['userid']) not in usuarios_moodle_no_borrables:
            # Antes de suspender a un alumno hay que suspender todas sus matrículas en cursos
            # pero HAY QUE mantenerlo en las cohortes ya que sacarlo puede borrar su progreso
            id_alumno = int(alumnoMoodle['userid'])
            cursos = get_cursos_en_que_esta_matriculado_un_alumno(moodle, id_alumno)
            escribeEnFichero(filename_md, "- Procesando a: " + repr(alumnoMoodle) )
            for curso in cursos:
                courseid = curso['courseid']
                suspende_matricula_en_curso(moodle, id_alumno, courseid)
                escribeEnFichero(filename_md, "  - id_alumno: " + str(id_alumno) + " matrícula suspendida en id_curso: " + str(courseid) )
                num_matriculas_suspendidas = num_matriculas_suspendidas + 1
            #

            desmatricula_alumno_de_todas_cohortes(moodle, id_alumno) # ¿¿ desmatricularlo de las cohortes hace que se pierda su progreso ??
            # escribeEnFichero(filename_html, "--- cohortes en las que figuraba eliminado:")
            suspende_alumno_moodle(alumnoMoodle['userid'], moodle)
            num_alumnos_suspendidos = num_alumnos_suspendidos + 1
            escribeEnFichero(filename_md, "  - estudiante suspendido")
            
            
        else:
            print("- Alumno configurado como NO borrable")
    
    ########################
    # Suspendo la matrícula en un curso de Moodle a aquellos alumnos que SIGAD me dice ya no deberían estar matriculados en un determinado curso
    # Los mantengo en las cohortes
    # Obtengo y recorro los usuarios de moodle. 
    # Itero sobre los alumnos y obtengo en qué están matriculados en moodle:
    # - si están matriculados en algo en que no estén matriculados en SIGAD les suspendo la matrícula
    # excepto si el shortname del curso termina en t (módulo de tutoría del ciclo)
    ########################
    alumnos_moodle = get_alumnos_moodle_no_borrados(moodle) 
    cursos_moodle = get_cursos(moodle)
    escribeEnFichero(filename_md, "\n### Alumnos a los que se ha suspendido su matrícula en algún curso pero no a ellos:\n")
    escribeEnFichero(filename_md, get_date_time_for_humans() + "\n")
    for alumno_moodle in alumnos_moodle:
        print("## Procesando alumno de Moodle")
        print(get_date_time_for_humans())
        print("- ", alumno_moodle['username'] )
        userid = alumno_moodle['userid']
        # no recorro los no borrables
        if int(userid) in usuarios_moodle_no_borrables: 
            continue
        username = alumno_moodle['username']
        # Obtengo los cursos en que este alumno moodle está matriculado en moodle
        cursos_matriculado = get_cursos_en_que_esta_matriculado(moodle, userid)
        print("  - Actualmente se encuentra matriculado en ", cursos_matriculado)
        # recorro los cursos en que el usuario de moodle está matriculado y miro si el usuario de sigad está matriculado en el curso o no
        for curso in cursos_matriculado:
            print("  - Procesando curso ", curso)
            courseid = curso['courseid']
            course_shortname = curso['shortname']
            course_codes = course_shortname.split("-") # 0 centreid 1 siglas ciclo 2 codigo materia

            # Si el curso es el de ayuda omitir comprobación. Están matriculados vía cohorte
            if course_shortname == "ayuda":
                continue;
            # Si el curso es el de tutoría omitir comprobación. Están matriculados vía cohorte
            if course_codes[2].count("t") == 1:
                continue;
            
            for alumno in alumnos_sigad:
                
                en_sigad_esta_matriculado = False
                if alumno.getDocumento() is not None and alumno.getDocumento().lower() == username.lower(): # he encontrado al alumno en SIGAD
                    print("  -", repr(alumno) )
                    print("  - El alumno", username, "está actualmente matriculado en moodle en el curso", course_shortname, ". Vamos a comprobar si en SIGAD también está")
                    
                    centros = alumno.getCentros()
                    print("  - Mirando centros del alumno")
                    for centro in centros:
                        if en_sigad_esta_matriculado:
                            break
                        if course_codes[0] == centro.get_codigo_centro(): #sigo profundizando
                            ciclos = centro.getCiclos()
                            print("  - Mirando ciclos del alumno")
                            for ciclo in ciclos:
                                if en_sigad_esta_matriculado:
                                    break;
                                if course_codes[1] == ciclo.get_siglas_ciclo(): #sigo profundizando
                                    modulos = ciclo.getModulos()
                                    print("  - Mirando módulos del alumno")
                                    if modulos is not None:
                                        for modulo in modulos:
                                            if en_sigad_esta_matriculado:
                                                break
                                            if int(course_codes[2]) == modulo.get_id_materia(): #he llegado al módulo
                                                en_sigad_esta_matriculado = True
                                                print("  - En SIGAD el alumno", username, "SI está matriculado en", course_shortname, "se le mantiene matriculado en moodle")
                                    else:
                                        print("  - No está en ningún módulo")
                                else:
                                    continue;
                        else:
                            continue
                    if not en_sigad_esta_matriculado:
                        print("  - En SIGAD el alumno", username, "NO está matriculado en", course_shortname, "se procede a suspender su matrícula en el curso de moodle")

                        # Casos especiales de fusión de cursos de Maite
                        # TODO Borrar el if para antes de empezar el curso 2026-2027
                        if course_shortname == "50020125-IFC301-5061" or course_shortname == "50020125-IFC302-5077" or course_shortname == "50020125-IFC303-5092" or course_shortname == "50020125-IFC201-5001":
                            continue;
                        # Fin del if que haría que borrar.

                        suspende_matricula_en_curso(moodle, userid, courseid)
                        # NO hay que sacarlo de la cohorte, eso borra progreso
                        escribeEnFichero(filename_md, "- " + username + "  matricula suspendida en " + course_shortname)
                        num_matriculas_suspendidas = num_matriculas_suspendidas + 1
                    break # una vez he procesado al alumno no tiene sentido seguir mirando los demás alumnos de SIGAD
    
    ########################
    # Proceso el fichero JSON (foto de SIGAD)
    # - si un alumno del fichero no existe en moodle lo creo
    # - matriculo a un alumno en los cursos que tenga asignados en SIGAD
    ########################
    escribeEnFichero(filename_md, "\n### Alumnos creados y matriculados:\n")
    escribeEnFichero(filename_md, get_date_time_for_humans() + "\n")
    usuarios_no_creables = [ ]
    # Creo diccionario de id_cursoshortname para evitar usar get_id_de_curso_by_shortname en cada iteración
    diccionario_cursos = {curso['shortname'] : curso['courseid'] for curso in cursos_moodle}
    diccionario_alumnos = {alumno['username'] : alumno['userid'] for alumno in alumnos_moodle}
    #
    escribeEnFichero(filename_csv, "First Name [Required],Last Name [Required],Email Address [Required],Password [Required],Password Hash Function [UPLOAD ONLY],Org Unit Path [Required],New Primary Email [UPLOAD ONLY],Recovery Email,Work Secondary Email,New Status [UPLOAD ONLY]")
    for alumno in alumnos_sigad:

        if SUBDOMAIN == "www" and num_emails_enviados >= 1000: # limitacion de 2.000 emails diarios en actual cuenta de gmail
            escribeEnFichero(filename_md, "\nALCANZADO LÍMITE DE ENVÍO DE EMAILS DIARIOS")
            escribeEnFichero(filename_md, "ALCANZADO LÍMITE DE ENVÍO DE EMAILS DIARIOS ")
            escribeEnFichero(filename_md, "ALCANZADO LÍMITE DE ENVÍO DE EMAILS DIARIOS\n")
            break

        if  SUBDOMAIN != "www" and num_emails_enviados >= 3: # limitacion de 10 emails para entornos que no sean producción.:
            escribeEnFichero(filename_md, "\nALCANZADO LÍMITE DE ENVÍO DE EMAILS DIARIOS")
            escribeEnFichero(filename_md, "ALCANZADO LÍMITE DE ENVÍO DE EMAILS DIARIOS ")
            escribeEnFichero(filename_md, "ALCANZADO LÍMITE DE ENVÍO DE EMAILS DIARIOS\n")
            break
        
        print("## Procesando alumno de fichero JSON")
        print(get_date_time_for_humans())
        print("- ", repr(alumno) )
        id_alumno = ""
        alumno_es_nuevo = False
        # Creo en moodle los alumnos que estén en el json y no estén en moodle
        if not existeAlumnoEnMoodle(moodle, alumno):
            print("  - Es nuevo")
            password = random_pass(10)
            try:
                # TODO: Comprobar al ir a crearlo si ya existe en moodle alguien con 
                # TODO: ese email corporativo. De ser así, modificarle el email corporativo
                # TODO: y volver a intentar crearlo. Repetir hasta éxito.
                id_alumno = crearAlumnoEnMoodle(moodle, alumno, password)
                num_alumnos_creados = num_alumnos_creados + 1
                escribeEnFichero(filename_md, "- Alumno " + alumno.getDocumento() + " creado.")
                matricula_alumno_en_cohorte_alumnado(moodle, id_alumno)
                alumno_es_nuevo = True
                
                # añadirlo al CSV de creación de cuentas 
                # TODO: tratar de crearlo vía API de google
                # https://support.google.com/a/answer/40057?hl=es&p=bulk_add_users&rd=1
                # First Name [Required],Last Name [Required],Email Address [Required],Password [Required],Password Hash Function [UPLOAD ONLY],Org Unit Path [Required],New Primary Email [UPLOAD ONLY],Recovery Email,Work Secondary Email
                escribeEnFichero(filename_csv,  alumno.getNombre() + "," + alumno.getApellidos() + "," + alumno.getEmailDominio() + "," + password + ",,/Alumnado,," + alumno.getEmailSigad()+ "," + alumno.getEmailSigad() + ",Active")


            except ValueError as e:
                usuarios_no_creables.append(alumno)
                continue
        else:
            print("  - Ya existía en moodle")
            #id_alumno = get_id_alumno_by_dni(moodle, alumno)
            id_alumno = diccionario_alumnos[ alumno.getDocumento().lower().rstrip() ]
            print("  - Tenía el id_alumno:", id_alumno);

        # Comprobamos que tenemos el id de alumno
        try:
            id_alumno = str(int(id_alumno))
        except ValueError:
            continue
        
        matriculado_en = [ ]
        # Revisar si está matriculado dónde corresponda y matricular
        for centro in alumno.getCentros():
            codigo_centro = centro.get_codigo_centro()
            for ciclo in centro.getCiclos():
                siglas_ciclo = ciclo.get_siglas_ciclo()
                matricula_alumno_en_cohorte(moodle, id_alumno, codigo_centro, siglas_ciclo)
                if ciclo.getModulos() is not None:
                    for modulo in ciclo.getModulos():
                        id_materia = modulo.get_id_materia()
                        print("  - Matriculando en ", id_materia )
                        shortname_curso = crearShortnameCurso(codigo_centro, siglas_ciclo, id_materia)
                        #id_curso = get_id_de_curso_by_shortname(moodle, shortname_curso)
                        id_curso = ""
                        try:
                            id_curso = diccionario_cursos[shortname_curso]
                        except KeyError:
                            id_curso = ""

                        print("id_curso ", id_curso )
                        if id_curso == "": # el curso no existe
                            print("  - El curso ", str(shortname_curso) , " no existe.", sep="")
                            escribeEnFichero(filename_md, "- Alumno "+ alumno.getDocumento()+ " NO puede matricularse en "+ shortname_curso + " por que el curso NO existe.")
                            num_alumnos_no_matriculados_en_cursos_inexistentes = num_alumnos_no_matriculados_en_cursos_inexistentes + 1
                        elif is_alumno_suspendido_en_curso(moodle, id_curso, id_alumno):
                            print("  - El alumno ", str(id_alumno) , " está suspendido en el curso ", str(shortname_curso),". Se le reactiva.", sep="")
                            reactiva_alumno_en_curso(moodle, id_alumno, id_curso)
                            num_matriculas_reactivadas = num_matriculas_reactivadas + 1;
                            escribeEnFichero(filename_md, "- Alumno "+ alumno.getDocumento()+ " reactivada su matricula en "+ shortname_curso + ".")
                            matriculado_en.append("- " + centro.get_centro() + " - " + ciclo.get_ciclo() + " - " + modulo.get_modulo() )
                        elif not is_alumno_matriculado_en_curso(moodle, id_alumno, id_curso):
                            print("  - El alumno ", str(id_alumno) , " NO está matriculado en el curso ", str(shortname_curso),". Se le matricula.", sep="")
                            matricula_alumno_en_curso(moodle, id_alumno, id_curso)
                            num_modulos_matriculados = num_modulos_matriculados + 1
                            escribeEnFichero(filename_md, "- Alumno "+ alumno.getDocumento()+ " matriculado en "+ shortname_curso + ".")
                            matriculado_en.append("- " + centro.get_centro() + " - " + ciclo.get_ciclo() + " - " + modulo.get_modulo() )
                        else:
                            print("  - El alumno (",id_alumno,") ya estaba matriculado en ", shortname_curso, sep="")
        # envío email
        if alumno_es_nuevo:
            time.sleep(2) # para no saturar el envío de emails
            matriculado_en_texto = "<br/>".join(matriculado_en)
            nombre = alumno.getNombre()
            apellidos = alumno.getApellidos()

            plantilla_path = Path("/var/fp-distancia-gestion-usuarios-automatica/templates/nuevoUsuario.html")
            plantilla = plantilla_path.read_text(encoding="utf-8")
            
            mensaje = plantilla.format(
                nombre=nombre,
                apellidos=apellidos,
                subdomain=SUBDOMAIN,
                usuario=alumno.getDocumento().lower(),
                contrasena=password,
                matriculado_en_texto=matriculado_en_texto,
                email=alumno.getEmailDominio(),
            )
            
            destinatario = "gestion@fpvirtualaragon.es"
            if SUBDOMAIN == "www":
                destinatario = alumno.getEmailSigad()
            else:
                print("Debería haberse enviado a '", alumno.getEmailSigad(), "'." )

            enviado = send_email( destinatario , "FP virtual - Aragón", mensaje)

            if enviado:
                num_emails_enviados = num_emails_enviados + 1
                print("num_emails_enviados: ", num_emails_enviados)
            else:
                num_emails_no_enviados = num_emails_no_enviados + 1
                print("Ha fallado el envío del email a '", destinatario, "'. Total fallos: '", num_emails_no_enviados, "'")
            
            
        else:
            if len(matriculado_en) > 0:
                matriculado_en_texto = "<br/>".join(matriculado_en)
                nombre = alumno.getNombre()
                apellidos = alumno.getApellidos()

                plantilla_path = Path("/var/fp-distancia-gestion-usuarios-automatica/templates/matriculasAnadidas.html")
                plantilla = plantilla_path.read_text(encoding="utf-8")

                mensaje = plantilla.format(
                    nombre = nombre, 
                    apellidos = apellidos, 
                    subdomain = SUBDOMAIN, 
                    matriculado_en_texto = matriculado_en_texto,
                )

                destinatario = "gestion@fpvirtualaragon.es"
                if SUBDOMAIN == "www":
                    destinatario = alumno.getEmailSigad()
                else:
                    print("Debería haberse enviado a '", alumno.getEmailSigad(), "'." )
                
                enviado = send_email( destinatario , "FP virtual - Aragón", mensaje)

                if enviado:
                    num_emails_enviados = num_emails_enviados + 1
                    print("num_emails_enviados: ", num_emails_enviados)
                else:
                    num_emails_no_enviados = num_emails_no_enviados + 1
                    print("Ha fallado el envío del email a '", destinatario, "'. Total fallos: '", num_emails_no_enviados, "'")

    # Evaluo alumnos con 2 tutorías o mas y los comparo con el fichero json origen a ver si están en las tutorías que les corresponde estar
    # suspendo las matrículas de las tutorías que no corresponda
    num_tutorias_suspendidas = eval_estudiantes_con_mas_de_1_tutorias(moodle, alumnos_sigad, filename_md)
    
    # Listo alumnos que no se han podido crear
    escribeEnFichero(filename_md, "\n### Alumnos que no se han podido crear\n")
    escribeEnFichero(filename_md, get_date_time_for_humans() + "\n")
    print("## Alumnos de SIGAD que no se han podido crear en Moodle")
    for alumno in usuarios_no_creables:
        print( "- ", repr(alumno) )
        escribeEnFichero(filename_md, "- " + repr(alumno) )
        num_alumnos_no_creables = num_alumnos_no_creables + 1

    ########################
    # En agosto todas las matrículas que están suspendidas las borramos
    ########################
    mes = get_mes()
    if mes == "08": 
        print("Agosto: se borran todas las matrículas suspendidas")
        matriculas = get_alumnos_con_matriculas_suspendidas_en_curso(moodle)
        for matricula in matriculas:
            courseid = matricula['courseid']
            studentid = matricula['studentid']
            desmatricula_alumno_en_curso(moodle, studentid, courseid)
            num_matriculas_borradas = num_matriculas_borradas + 1

    ########################
    # Añado un resumen al final del mensaje
    ########################
    escribeEnFichero(filename_md, "\n--------------------------------------------------------------------------")
    escribeEnFichero(filename_md, "--------------------------------------------------------------------------")
    escribeEnFichero(filename_md, "--------------------------------------------------------------------------\n")
    escribeEnFichero(filename_md, "\n## RESUMEN de acciones llevadas a cabo por este script:\n")
    escribeEnFichero(filename_md, "- Alumnos existentes en moodle antes de ejecutar este programa: " + str(num_alumnos_pre_app) )
    num_alumnos_post_script = len( get_alumnos_moodle_no_borrados(moodle) )
    escribeEnFichero(filename_md, "- Alumnos existentes en moodle despues de ejecutar este programa: " + str(num_alumnos_post_script) )
    escribeEnFichero(filename_md, "- Alumnos creados por este script: " + str(num_alumnos_creados) )
    escribeEnFichero(filename_md, "- Alumnos que NO es posible crear por este script: " + str(num_alumnos_no_creables) )
    escribeEnFichero(filename_md, "- Alumnos reactivados por este script: " + str(num_alumnos_reactivados) )
    escribeEnFichero(filename_md, "- Alumnos suspendidos por este script: " + str(num_alumnos_suspendidos) )
    escribeEnFichero(filename_md, "- Alumnos cuyo login ha sido modificado por este script: " + str(num_alumnos_modificado_login) )
    escribeEnFichero(filename_md, "- Alumnos cuyo email ha sido modificado por este script: " + str(num_alumnos_modificado_email) )
    escribeEnFichero(filename_md, "- Cantidad de matriculas hechas en modulos: " + str(num_modulos_matriculados) )
    escribeEnFichero(filename_md, "- Cantidad de matriculas reactivadas en modulos: " + str(num_matriculas_reactivadas) )
    escribeEnFichero(filename_md, "- Cantidad de matriculas suspendidas en modulos (no cuenta en las tutorías): " + str(num_matriculas_suspendidas) )
    escribeEnFichero(filename_md, "- Cantidad de matriculas borradas en tutorías (vía eliminación estudiante de cohorte): " + str(num_tutorias_suspendidas) )
    escribeEnFichero(filename_md, "- Cantidad de matriculas borradas en modulos (solo en Agosto): " + str(num_matriculas_borradas) )
    escribeEnFichero(filename_md, "- Cantidad de matriculas no hechas por no existir el curso destino: " + str(num_alumnos_no_matriculados_en_cursos_inexistentes) )
    escribeEnFichero(filename_md, "- Cantidad de emails enviados: " + str(num_emails_enviados) )
    escribeEnFichero(filename_md, "- Cantidad de emails NO enviados: " + str(num_emails_no_enviados) )
    ########################
    # Envío email resumen de lo hecho por email a responsables
    ########################
    time.sleep(5)
    print("Printed after 5 seconds.")

    plantilla_path = Path("/var/fp-distancia-gestion-usuarios-automatica/templates/informeAutomatizado.html")
    plantilla = plantilla_path.read_text(encoding="utf-8")

    mensaje = plantilla.format(
        subdomain = SUBDOMAIN,
        filename_md = filename_md,
        filename_csv = filename_csv
    )

    emails = REPORT_TO.split()
    for email in emails:
        send_email_con_adjuntos(email, "Informe automatizado gestión automática usuarios moodle", mensaje, [filename_md, filename_csv] )

    #
    # End of main 
    # 

#################################
#################################
#################################
# Funciones
#################################
#################################
#################################

def escribeEnFichero(nombre_fichero, linea):
    """
    Escribe en el fichero indicado en nombre_fichero la linea indicada, sin sobreescribir lo que ya hubiera.
    """
    with open(nombre_fichero, "a", encoding="utf-8") as f:
        f.write(linea + "\n")

def eval_estudiantes_con_mas_de_1_tutorias(moodle, alumnos_sigad, filename_md):
    """
    Procesa a los estudiantes de Moodle que están matriculados en 2 o mas tutorías y verifica si en el 
    fichero de JSON original también están en 2 o mas ciclos
    """
    print("eval_estudiantes_con_mas_de_1_tutorias(...)")
    estudiantes = get_estudiantes_con_mas_de_1_tutorias(moodle)
    num_tutorias_suspendidas = 0
    # Aquellos estudiantes que tengan 2 o mas tutorías los busco en los datos que han llegado de 
    # SIGAD y compruebo si están dónde deberían estar o no y los mantengo en la cohorte o no
    print("Estudiantes con 2 tutorías o mas")
    escribeEnFichero(filename_md, "\n### Alumnos con mas de 1 tutoría:\n")
    escribeEnFichero(filename_md, get_date_time_for_humans() + "\n")
    for estudianteMoodle in estudiantes:
        print("- Evaluando estudiante: ", estudianteMoodle)
        escribeEnFichero(filename_md, "- Evaluando a: " + estudianteMoodle['username'])
        encontrado = False
        for alumno_sigad in alumnos_sigad:
            # print("alumno_sigad.getDocumento()", alumno_sigad.getDocumento())
            if estudianteMoodle['username'] is not None \
                    and alumno_sigad.getDocumento() is not None \
                    and estudianteMoodle['username'].lower() == alumno_sigad.getDocumento().lower():
                print("Estudiante ENCONTRADO en SIGAD")
                
                cursos = get_cursos_de_tutoria_en_que_esta_matriculado_un_alumno(moodle, estudianteMoodle['userid'])
                print("Cursos de tutoría en que está matriculado el alumno en Moodle: ", cursos)
                
                # Recorrer los cursos en que está matriculado en SIGAD y su shortname tiene una t
                # Por cada curso ver si en los datos de SIGAD estámatriculado en ese centro y ciclo
                for curso in cursos:
                    print("- Evaluando si en SIGAD está en Curso: ", str(curso))
                    
                    codCentro = curso['cshortname'].split("-")[0]
                    codCiclo = curso['cshortname'].split("-")[1]
                    le_correspone_la_tutoria = False
                    # Buscar en los datos de SIGAD si el curso está matriculado en ese centro y ciclo
                    for centro in alumno_sigad.getCentros():
                        print("centro.get_codigo_centro(): ", centro.get_codigo_centro())
                        print("codCentro:", codCentro)
                        if centro.get_codigo_centro() == codCentro:
                            for ciclo in centro.getCiclos():
                                print("ciclo.get_siglas_ciclo: ", ciclo.get_siglas_ciclo())
                                print("codCiclo:", codCiclo)
                                if ciclo.get_siglas_ciclo() == codCiclo:
                                    le_correspone_la_tutoria = True
                                    break
                    # Si no está matriculado en ese centro y ciclo, lo desmatriculo de esa tutoria
                    if not le_correspone_la_tutoria:
                        print("No está matriculado en ese centro (",codCentro,") y ciclo(",codCiclo,"). Borrando matrícula de esa tutoría vía eliminación del estddiante de la cohorte.")
                        escribeEnFichero(filename_md, "  - No está matriculado en ese centro ("+codCentro+") y ciclo ("+codCiclo+"). Borrando matrícula de esa tutoría vía eliminación del estddiante de la cohorte.")
                        cohort_id = get_cohort_id(moodle, codCentro+"-"+codCiclo)
                        borra_alumno_de_cohorte(moodle, cohort_id, estudianteMoodle['userid'])
                        num_tutorias_suspendidas += 1
                        print("borrado estudiante de cohorte: " + codCentro+"-"+codCiclo + "(" + str(cohort_id) + ")")
                        escribeEnFichero(filename_md, "  - Borrado estudiante de cohorte: " + codCentro+"-"+codCiclo + "(" + str(cohort_id) + ")")
                    else:
                        print("Está matriculado correctamente en esa tutoría ",codCentro, codCiclo, ". No hago nada")
                        escribeEnFichero(filename_md, "  - Está matriculado correctamente en esa tutoría ("+codCentro+"-"+codCiclo+"). No hago nada")
                # 
                encontrado = True
                break
        if not encontrado:
            print("Estudiante NO ENCONTRADO en SIGAD")
            escribeEnFichero(filename_md, "  - Estudiante NO ENCONTRADO en SIGAD")

    return num_tutorias_suspendidas
    # raise Exception("Fin de eval_estudiantes_con_mas_de_1_tutorias") # para testing

def get_estudiantes_con_mas_de_1_tutorias(moodle):
    """
    Devuelve una lista de estudiantes que tienen más de 2 tutorias
    """
    
    print("get_estudiantes_con_mas_de_1_tutorias(...)")

    command = '''\
            mysql --user=\"{DB_USER}\" --password=\"{DB_PASS}\" --host=\"{DB_HOST}\" -D \"{DB_NAME}\"  --execute=\"
                SELECT
                    u.id, u.username
                                                
                FROM
                    mdl_role_assignments ra
                    JOIN mdl_user u ON u.id = ra.userid
                    JOIN mdl_role r ON r.id = ra.roleid
                    JOIN mdl_context cxt ON cxt.id = ra.contextid
                    JOIN mdl_course c ON c.id = cxt.instanceid

                WHERE ra.userid = u.id
                                                
                    AND ra.contextid = cxt.id
                    AND cxt.contextlevel =50
                    AND cxt.instanceid = c.id
                    AND  roleid = 5
                    and c.shortname like '%t'
                    AND u.username not like 'prof%'

                group by u.id
                having  count(*) > 1
            \" | tail -n +2
            '''.format(DB_USER = DB_USER, DB_PASS = DB_PASS, DB_HOST = DB_HOST, DB_NAME = DB_NAME )
    
    cursos_en_los_que_esta_matriculado = run_command( command, True ).rstrip()
    
    estudiantes = []    
    
    data_s = io.StringIO(cursos_en_los_que_esta_matriculado).read()
    lines = data_s.splitlines()
    estudiante = [
        {
            "userid": line.split()[0],
            "username": line.split()[1],
        }
        for line in lines
        # if line.split()[-1].endswith("moodle_1")
    ]
    estudiantes.extend(estudiante)
    

    return estudiantes

def get_cursos_de_tutoria_en_que_esta_matriculado_un_alumno(moodle, id_alumno):
    """
    Devuelve una lista los cursos de tutoría en que un alumno está matriculado sin tener la matrícula suspendida
    """
    print("get_cursos_de_tutoria_en_que_esta_matriculado_un_alumno(...)")

    command = '''\
            mysql --user=\"{DB_USER}\" --password=\"{DB_PASS}\" --host=\"{DB_HOST}\" -D \"{DB_NAME}\"  --execute=\"
                SELECT c.id, ue.userid, c.shortname, c.fullname
                FROM mdl_user_enrolments ue 
                INNER JOIN mdl_enrol e ON e.id = ue.enrolid 
                INNER JOIN mdl_course c ON e.courseid = c.id 
                where ue.status = 0 and ue.userid = {id_alumno} and c.shortname like '%t';
            \" | tail -n +2
            '''.format(DB_USER = DB_USER, DB_PASS = DB_PASS, DB_HOST = DB_HOST, DB_NAME = DB_NAME, id_alumno = id_alumno )

    alumnos_con_matriculas_suspendidas_en_curso = run_command( command , True).rstrip()
    
    matriculas = []    
    
    data_s = io.StringIO(alumnos_con_matriculas_suspendidas_en_curso).read()
    lines = data_s.splitlines()
    matricula = [
        {
            "courseid": line.split()[0],
            "studentid": line.split()[1],
            "cshortname": line.split()[2],
            "cfullname": line.split()[3],
        }
        for line in lines
        # if line.split()[-1].endswith("moodle_1")
    ]
    matriculas.extend(matricula)
    print("matriculas: ", matriculas )

    return matriculas
    # End of get_cursos_de_tutoria_en_que_esta_matriculado_un_alumno

def random_pass(str_size):
    """
    devuelve una cadena aleatoria de la longitud dada de entre los caracteres existentes en allowed_chars
    """
    allowed_chars = "ABCDEFGHJKLMNPRSTUVW23456789"
    return ''.join(random.choice(allowed_chars) for x in range(str_size))

def get_mes():
    """
    devuelve el mes
    """
    now = datetime.now() # current date and time
    mes = now.strftime("%m")
    return mes

def get_curso_para_REST():
    """
    será un valor variable para indicar el curso escolar del que se solicitan datos. 
    Por ejemplo, para solicitar los datos del curso escolar 2020/2021 habrá que utilizar el valor 2020
    """
    now = datetime.now() # current date and time
    anio = now.strftime("%Y")
    mes = now.strftime("%m")
    if int(mes) in [1,2,3,4,5,6,7,8]:
        return str( int(anio) - 1 )
    else:
        return anio

def reactiva_usuario(moodle, id_usuario):
    """
    Reactiva a un usuario que estuviese suspendido
    """
    print("reactiva_usuario(...)")

    command = '''\
            mysql --user=\"{DB_USER}\" --password=\"{DB_PASS}\" --host=\"{DB_HOST}\" -D \"{DB_NAME}\"  --execute=\"
                update mdl_user
                set suspended = 0
                WHERE id = {id_usuario}
            \" 
            '''.format(DB_USER = DB_USER, DB_PASS = DB_PASS, DB_HOST = DB_HOST, DB_NAME = DB_NAME, id_usuario = id_usuario )
    run_command( command , False)
    
    #
    # End of reactiva_usuario
    #

def get_cursos_en_que_esta_matriculado(moodle, id_usuario):
    """
    Devuelve una lista de cursos en los que el alumno está matriculado
    """
    print("get_cursos_en_que_esta_matriculado(id_usuario: ", id_usuario, ")", sep="")

    command = '''\
            mysql --user=\"{DB_USER}\" --password=\"{DB_PASS}\" --host=\"{DB_HOST}\" -D \"{DB_NAME}\"  --execute=\"
                SELECT c.id, c.shortname 
                FROM mdl_user u 
                INNER JOIN mdl_user_enrolments ue ON ue.userid = u.id 
                INNER JOIN mdl_enrol e ON e.id = ue.enrolid 
                INNER JOIN mdl_course c ON e.courseid = c.id 
                WHERE u.id = {id_usuario}
            \" | tail -n +2
            '''.format(DB_USER = DB_USER, DB_PASS = DB_PASS, DB_HOST = DB_HOST, DB_NAME = DB_NAME, id_usuario = id_usuario )
    cursos_en_los_que_esta_matriculado = run_command( command , True).rstrip()
    
    cursos = []    
    
    data_s = io.StringIO(cursos_en_los_que_esta_matriculado).read()
    print("data_s: ", data_s, sep="")
    lines = data_s.splitlines()
    print("Número de líneas: ", len(lines), sep="")
    curso = [
        {
            "courseid": line.split()[0],
            "shortname": line.split()[1],
        }
        for line in lines
        # if line.split()[-1].endswith("moodle_1")
    ]
    cursos.extend(curso)
    

    return cursos
    # End of get_cursos_en_que_esta_matriculado

def get_cursos_en_que_esta_matriculado_un_alumno(moodle, id_alumno):
    """
    Devuelve una lista los cursos en que un alumno está matriculado sin tener la matrícula suspendida
    """
    print("get_cursos_en_que_esta_matriculado_un_alumno(...)")

    command = '''\
            mysql --user=\"{DB_USER}\" --password=\"{DB_PASS}\" --host=\"{DB_HOST}\" -D \"{DB_NAME}\"  --execute=\"
                SELECT c.id, ue.userid, c.shortname, c.fullname
                FROM mdl_user_enrolments ue 
                INNER JOIN mdl_enrol e ON e.id = ue.enrolid 
                INNER JOIN mdl_course c ON e.courseid = c.id
                where ue.status = 0 and ue.userid = {id_alumno} ;
            \" | tail -n +2
            '''.format(DB_USER = DB_USER, DB_PASS = DB_PASS, DB_HOST = DB_HOST, DB_NAME = DB_NAME, id_alumno = id_alumno )

    alumnos_con_matriculas_suspendidas_en_curso = run_command( command , True).rstrip()
    
    matriculas = []    
    
    data_s = io.StringIO(alumnos_con_matriculas_suspendidas_en_curso).read()
    lines = data_s.splitlines()
    matricula = [
        {
            "courseid": line.split()[0],
            "studentid": line.split()[1],
            "cshortname": line.split()[2],
            "cfullname": line.split()[3],
        }
        for line in lines
        # if line.split()[-1].endswith("moodle_1")
    ]
    matriculas.extend(matricula)
    print("matriculas: ", matriculas )

    return matriculas
    # End of get_cursos_en_que_esta_matriculado_un_alumno


def get_alumnos_con_matriculas_suspendidas_en_curso(moodle):
    """
    Devuelve una lista de matrículas con el par idcurso idalumno
    """
    print("get_alumnos_con_matriculas_suspendidas_en_curso(...)")

    command = '''\
            mysql --user=\"{DB_USER}\" --password=\"{DB_PASS}\" --host=\"{DB_HOST}\" -D \"{DB_NAME}\"  --execute=\"
                SELECT c.id, ue.userid
                FROM mdl_user_enrolments ue 
                INNER JOIN mdl_enrol e ON e.id = ue.enrolid 
                INNER JOIN mdl_course c ON e.courseid = c.id
                where ue.status = 1;
            \" | tail -n +2
            '''.format(DB_USER = DB_USER, DB_PASS = DB_PASS, DB_HOST = DB_HOST, DB_NAME = DB_NAME )

    alumnos_con_matriculas_suspendidas_en_curso = run_command( command , True).rstrip()
    
    matriculas = []    
    
    data_s = io.StringIO(alumnos_con_matriculas_suspendidas_en_curso).read()
    lines = data_s.splitlines()
    matricula = [
        {
            "courseid": line.split()[0],
            "studentid": line.split()[1],
        }
        for line in lines
        # if line.split()[-1].endswith("moodle_1")
    ]
    matriculas.extend(matricula)
    

    return matriculas
    # End of get_alumnos_con_matriculas_suspendidas_en_curso

def update_moodle_username(moodle, userid, username_nuevo):
    """
    En el moodle dado actualiza el usuario userid a un nuevo username
    """
    print("update_moodle_username(userid: '", userid, "', username_nuevo: '",username_nuevo,"')", sep="")

    command = '''\
            mysql --user=\"{DB_USER}\" --password=\"{DB_PASS}\" --host=\"{DB_HOST}\" -D \"{DB_NAME}\"  --execute=\"
                update mdl_user  
                set username = '{username_nuevo}'
                WHERE id = {userid}
            \"
            '''.format(DB_USER = DB_USER, DB_PASS = DB_PASS, DB_HOST = DB_HOST, DB_NAME = DB_NAME, username_nuevo = username_nuevo, userid = userid )
    run_command( command, False )

def update_moodle_email_sigad(userid, email_nuevo):
    """
    En el moodle dado actualiza el email de sigad a userid
    """
    print("update_moodle_email_sigad(...)")
    
    command = '''\
            mysql --user=\"{DB_USER}\" --password=\"{DB_PASS}\" --host=\"{DB_HOST}\" -D \"{DB_NAME}\"  --execute=\"
                update mdl_user_info_data  
                set data = '{email_nuevo}'
                WHERE fieldid = 4 and userid = {userid}
            \"
            '''.format(DB_USER = DB_USER, DB_PASS = DB_PASS, DB_HOST = DB_HOST, DB_NAME = DB_NAME, email_nuevo = email_nuevo, userid = userid )

    devuelto = run_command( command, True )
    # print(" devuelto " + devuelto)

def get_date_time():
    """
    return the datetime in format yyyymmddhhmmss
    info from  https://www.programiz.com/python-programming/datetime/strftime
    """
    now = datetime.now() # current date and time
    return now.strftime("%Y%m%d-%H%M%S")

def get_date_time_for_humans():
    """
    return the datetime in format dd/mm/yyyy hh:mm:ss
    info from  https://www.programiz.com/python-programming/datetime/strftime
    """
    now = datetime.now() # current date and time
    return now.strftime("%d/%m/%Y %H:%M:%S")

def get_date_time_for_filename():
    """
    return the datetime in format yyyy_mm_dd_hh_mm_ss_
    info from  https://www.programiz.com/python-programming/datetime/strftime
    """
    now = datetime.now() # current date and time
    return now.strftime("%Y_%m_%d_%H_%M_%S_")

def abre_fichero(nombre_fichero):
    """
    Abre el fichero dado y devuelve su contenido
    """
    print("abre_fichero(" + nombre_fichero + ")")
    # open the file nombre_fichero and return its contents
    with open(PATH + "logs/" + nombre_fichero, "r") as f:
        return f.read()

def guarda_fichero_respuesta_ws1(nombre_fichero, contenido):
    """
    Guarda en disco duro, en la carpeta logs un fichero con el nombre indicado en parámetro y el contenido dado
    """
    print("guarda_fichero_respuesta_ws1(...)")
    data = json.loads(contenido.decode("utf-8"))
    with open(PATH + "logs/" + SUBDOMAIN + "/json/" + nombre_fichero, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def guarda_fichero_respuesta_ws2(nombre_fichero, contenido):
    """
    Guarda en disco duro, en la carpeta logs un fichero con el nombre indicado en parámetro y el contenido dado
    """
    print("guarda_fichero_respuesta(...)")
    data = json.loads(contenido.decode("utf-8"))
    data["estudiantes"] = json.loads(data["estudiantes"])
    with open(PATH + "logs/" + SUBDOMAIN + "/json/" + nombre_fichero, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_moodle(subdomain):
    """
    Devuelve un objeto como el siguiente:
    #
    """
    print("get_moodle(subdomain: ",subdomain,")", sep="")
    # urls = []
    
    data = os.popen(f"docker ps | grep {subdomain}").read()
    data_s = io.StringIO(data).read()
    lines = data_s.splitlines()
    container = [
        {
            "url": line.split()[-1].replace("wwwfpvirtualaragones-moodle-1", ".fpvirtualaragon.es"), # "url": line.split()[-1].replace("adistanciafparagones-moodle-1", ".adistanciafparagon.es"),
            "container_name": line.split()[-1],
        }
        for line in lines
        if line.split()[-1].endswith("moodle-1")
    ]
    # urls.extend(container)

    return container

def run_moosh_command(moodle, command, capture=False, timeout=10):
    print("run_moosh_command(...)")
    print("command:", command)

    command_string = f"docker exec {moodle['container_name']} {command}"

    try:
        if capture:
            result = subprocess.run(
                command_string,
                shell=True,           # interpreta el comando como string
                capture_output=True,  # captura stdout y stderr
                text=True,            # salida en str
                timeout=timeout       # segundos máximo
            )
            return result.stdout
        else:
            subprocess.run(
                command_string,
                shell=True,
                timeout=timeout
            )
    except subprocess.TimeoutExpired:
        print(f"⏱️ El comando tardó más de {timeout} segundos y fue cancelado.")
        return ""


def run_command(command, capture=False, timeout=10):
    print("run_command(...)")
    print("command:", command)

    try:
        if capture:
            result = subprocess.run(
                command,
                shell=True,           # mantiene compatibilidad con tu string de comando
                capture_output=True,  # guarda stdout y stderr
                text=True,            # convierte a str
                timeout=timeout       # segundos máximo
            )
            return result.stdout
        else:
            subprocess.run(
                command,
                shell=True,
                timeout=timeout
            )
    except subprocess.TimeoutExpired:
        print(f"⏱️ El comando tardó más de {timeout} segundos y fue cancelado.")
        return ""

def matricula_alumno_en_cohorte_alumnado(moodle, id_alumno):
    """
    Añade al alumno dado en la cohorte alumnado
    """
    print("matricula_alumno_en_cohorte_alumnado(...)")
    cmd = "moosh -n cohort-enrol -u " + id_alumno + " \"alumnado\""
    run_moosh_command(moodle, cmd, False)

def borra_alumno_de_cohorte(moodle, id_cohort, id_alumno):
    """
    Borra alumno de cohorte
    """
    print("borra_alumno_de_cohorte(...)")
    command = '''\
            mysql --user=\"{DB_USER}\" --password=\"{DB_PASS}\" --host=\"{DB_HOST}\" -D \"{DB_NAME}\"  --execute=\"
                delete from mdl_cohort_members
                where cohortid = {id_cohort} and userid = {id_alumno}
            \"
            '''.format(DB_USER = DB_USER, DB_PASS = DB_PASS, DB_HOST = DB_HOST, DB_NAME = DB_NAME, id_cohort = id_cohort, id_alumno = id_alumno )
    run_command( command, False )   

def desmatricula_alumno_de_todas_cohortes(moodle, id_alumno):
    """
    Elimina al alumno dado de todas las cohortes a las que pertenezca
    """
    print("desmatricula_alumno_de_todas_cohortes(...)")

    command = '''\
            mysql --user=\"{DB_USER}\" --password=\"{DB_PASS}\" --host=\"{DB_HOST}\" -D \"{DB_NAME}\"  --execute=\"
                delete from mdl_cohort_members
                where userid = {id_alumno}
            \"
            '''.format(DB_USER = DB_USER, DB_PASS = DB_PASS, DB_HOST = DB_HOST, DB_NAME = DB_NAME, id_alumno = id_alumno )
    run_command( command, False )   

def matricula_alumno_en_cohorte(moodle, id_alumno, cod_centro, id_estudio):
    """
    Dado un alumno y un curso los desmatricula en el moodle dado
    """
    print("matricula_alumno_en_cohorte(...)")
    cmd = "moosh -n cohort-enrol -u " + id_alumno + " \"" + cod_centro + "-" + id_estudio + "\""
    run_moosh_command(moodle, cmd, False)

def desmatricula_alumno_en_curso(moodle, id_alumno, id_curso):
    """
    Dado un alumno y un curso los desmatricula en el moodle dado
    """
    print("desmatricula_alumno_en_curso(...)")

    cmd = "moosh -n course-unenrol " + id_curso + " " + id_alumno
    run_moosh_command(moodle, cmd, False)

def suspende_matricula_en_curso(moodle, id_alumno, id_curso):
    """
    Dado un alumno y un curso suspende la matrícula en el moodle dado
    """
    print("suspende_matricula_en_curso(...)")

    command = '''\
            mysql --user=\"{DB_USER}\" --password=\"{DB_PASS}\" --host=\"{DB_HOST}\" -D \"{DB_NAME}\"  --execute=\"
                update mdl_user_enrolments ue 
                set ue.status = 1 
                where ue.userid = {id_alumno} and ue.enrolid in 
                    (select e.id
                    from mdl_enrol e 
                    where e.courseid = {id_curso}  )
            \"
            '''.format(DB_USER = DB_USER, DB_PASS = DB_PASS, DB_HOST = DB_HOST, DB_NAME = DB_NAME, id_alumno = id_alumno, id_curso = id_curso )
    run_command( command, False )
    # Fin de suspende_matricula_en_curso

def reactiva_alumno_en_curso(moodle, id_alumno, id_curso):
    """
    Dado un alumno y un curso reactiva su matrícula en el moodle dado
    """
    print("reactiva_alumno_en_curso(...)")

    command = '''\
            mysql --user=\"{DB_USER}\" --password=\"{DB_PASS}\" --host=\"{DB_HOST}\" -D \"{DB_NAME}\"  --execute=\"
                update mdl_user_enrolments ue 
                set ue.status = 0 
                where ue.userid = {id_alumno} and ue.enrolid in 
                    (select e.id
                    from mdl_enrol e 
                    where e.courseid = 
                        (select c.id 
                        from mdl_course c 
                        where c.id = {id_curso})  )
            \"
            '''.format(DB_USER = DB_USER, DB_PASS = DB_PASS, DB_HOST = DB_HOST, DB_NAME = DB_NAME, id_alumno = id_alumno, id_curso = id_curso )
    run_command( command, False )
    # Fin de reactiva_alumno_en_curso

def matricula_alumno_en_curso(moodle, id_alumno, id_curso):
    """
    Dado un alumno y un curso los matricula en el moodle dado
    """
    print("matricula_alumno_en_curso(...)")

    cmd = "moosh -n course-enrol -i " + id_curso + " " + id_alumno
    run_moosh_command(moodle, cmd, False)

def get_id_alumno_by_dni(moodle, alumno):
    """
    Dado el dni/nie/... de un alumno (su login) devuelve el id que tiene en moodle
    """
    print("get_id_alumno_by_dni(...)")

    cmd = "moosh -n user-list -n 50000 | grep " + alumno.getDocumento().lower() + " | cut -d \",\" -f 1 | cut -d \"(\" -f 2 | sed 's/)//' "
    id_alumno = run_moosh_command(moodle, cmd, True).rstrip()
    print("id_alumno: ", id_alumno)
    return id_alumno


def is_alumno_suspendido_en_curso(moodle, id_curso, id_usuario):
    """
    Devuelve verdadero si el alumno dado está suspendido en el curso dado
    """
    print(f"is_alumno_suspendido_en_curso(id_curso: {id_curso}, id_usuario: {id_usuario})")

    if id_usuario is None or id_usuario == "":
        print("WARNING!!! Esto no debería ocurrir: id_usuario es None o cadena vacía")
        return False

    # En la SQL: ue.status -- suspendido = 1 activado = 0
    command = '''\
            mysql --user=\"{DB_USER}\" --password=\"{DB_PASS}\" --host=\"{DB_HOST}\" -D \"{DB_NAME}\"  --execute=\"
                SELECT ue.status
                FROM mdl_user_enrolments ue
                JOIN mdl_enrol e ON ue.enrolid = e.id
                where ue.userid = {id_usuario} and e.courseid = {id_curso} 
            \" | tail -n +2
            '''.format(DB_USER = DB_USER, DB_PASS = DB_PASS, DB_HOST = DB_HOST, DB_NAME = DB_NAME, id_usuario = id_usuario, id_curso = id_curso )

    is_alumno_suspendido_en_curso = run_command( command , True).rstrip()
    
    print("is_alumno_suspendido_en_curso: ", is_alumno_suspendido_en_curso)

    if is_alumno_suspendido_en_curso == "1":
        return True
    return False
    # End of is_alumno_suspendido_en_curso

def get_cohort_id(moodle, name):
    """
    Devuelve el id de la cohorte cuyo nombre sea el dado
    """
    print("get_cohort_id(...)")

    command = '''\
            mysql --user=\"{DB_USER}\" --password=\"{DB_PASS}\" --host=\"{DB_HOST}\" -D \"{DB_NAME}\"  --execute=\"
                SELECT id
                FROM mdl_cohort
                where name = '{name}' 
            \" | tail -n +2
            '''.format(DB_USER = DB_USER, DB_PASS = DB_PASS, DB_HOST = DB_HOST, DB_NAME = DB_NAME, name = name )

    cohort_id = run_command( command , True).rstrip()
    
    print("cohort_id: ", cohort_id)
    
    return cohort_id
    # End of is_alumno_suspendido_en_curso

def is_alumno_matriculado_en_curso(moodle, id_alumno, id_curso):
    """
    Dado un moodle, un id_alumno y un curso devuelve:
    - True si el id_alumno existe en el curso
    - False si el id_alumno no existe en el curso
    """
    print("is_alumno_matriculado_en_curso(id_alumno: ", id_alumno, ", id_curso: ", id_curso, ")", sep="" )

    cmd = "moosh -n user-list --course " + id_curso + " | grep \"(" + id_alumno + ")\" "
    out = run_moosh_command(moodle, cmd, True).rstrip()
    print("out: ", out)
    if out == "":
        return False
    else:
        return True

from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import smtplib, ssl

def send_email_con_adjuntos(destinatario, asunto, html, filenames):
    """
    Envía un correo con uno o varios ficheros adjuntos.
    - destinatario: dirección del receptor
    - asunto: asunto del correo
    - filenames: lista de rutas a los ficheros adjuntos
    """
    print(f"send_email_con_adjuntos(destinatario: '{destinatario}', archivos: {filenames})")

    enviado = False
    port = SMTP_PORT
    smtp_server = SMTP_HOSTS
    sender_email = SMTP_USER
    receiver_email = destinatario
    password = SMTP_PASSWORD

    # Crear mensaje
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = asunto

    message.attach(MIMEText(html, "html")) # parte HTML

    # Adjuntar cada fichero
    for filename in filenames:
        try:
            with open(filename, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                # Solo el nombre del archivo, no la ruta completa
                nombre_archivo = filename.split('/')[-1]  
                part.add_header('Content-Disposition', f'attachment; filename="{nombre_archivo}"')
                message.attach(part)
        except Exception as e:
            print(f"Error al adjuntar {filename}: {e}")

    # Enviar mensaje
    my_message = message.as_string()
    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_server, port) as server:
        try:
            server.starttls(context=context)
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, my_message)
            enviado = True
        except Exception as e:
            print(f"Error al enviar el correo: {e}")
        finally:
            server.quit()
    return enviado


import smtplib, ssl
from email.message import EmailMessage
from email.headerregistry import Address

def send_email(destinatario, asunto, html):
    port = SMTP_PORT
    smtp_server = SMTP_HOSTS
    sender_email = SMTP_USER
    password = SMTP_PASSWORD

    msg = EmailMessage()
    msg['Subject'] = asunto                # se codifica bien
    msg['From'] = sender_email
    msg['To'] = destinatario
    msg.set_content("Tu cliente no soporta HTML.")   # parte de texto plano
    msg.add_alternative(html, subtype='html')        # parte HTML

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_server, port) as server:
        try:
            server.starttls(context=context)
            server.login(sender_email, password)
            server.send_message(msg)  # <- evita concatenaciones manuales
            return True
        except Exception as e:
            print(e)
            return False


def suspende_alumno_moodle(id_usuario, moodle):
    """
    suspende a un usuario que estuviese suspendido
    """
    print("suspende_alumno_moodle(...)")

    command = '''\
            mysql --user=\"{DB_USER}\" --password=\"{DB_PASS}\" --host=\"{DB_HOST}\" -D \"{DB_NAME}\"  --execute=\"
                update mdl_user
                set suspended = 1
                WHERE id = {id_usuario}
            \" 
            '''.format(DB_USER = DB_USER, DB_PASS = DB_PASS, DB_HOST = DB_HOST, DB_NAME = DB_NAME, id_usuario = id_usuario )
    run_command( command , False)
    #
    # End of suspende_alumno_moodle
    #

def get_id_de_curso_by_shortname(moodle, shortname):
    """
    Dado un moodle y un shotname devuelve el id del curso si el mismo existe
    """
    print("get_id_de_curso_by_shortname(...)")
    cmd = "moosh -n course-list \"shortname = '" + shortname + "'\" | tail -n 1 | cut -d \",\" -f1 | sed 's/\"//' | sed 's/\"//' " 
    id_course = run_moosh_command(moodle, cmd, True).rstrip()

    print("id_course: ", id_course)

    return id_course

def get_alumnos_suspendidos(moodle):
    print("get_alumnos_suspendidos(...)")
    """
    Devuelve una lista de alumnos (omite usuarios con username que empiece por prof) que actualmente están en moodle suspendidos
    #
    """
    cmd = "moosh -n user-list -n 50000 \"suspended = 1 and username not like 'prof%' \" " #listado de usuarios limitado a 50.000 # username (id), email,
    alumnos_moodle = run_moosh_command(moodle, cmd, True)
    
    alumnos = []    
    
    data_s = io.StringIO(alumnos_moodle).read()
    lines = data_s.splitlines()
    alumno = [
        {
            "username": line.split()[0],
            "userid": line.split()[1].replace("(","").replace("),",""),
            "email": line.split()[2].replace(",",""),
        }
        for line in lines
    ]
    alumnos.extend(alumno)

    return alumnos
    #
    # End of get_alumnos_suspendidos
    #

def get_alumnos_moodle_no_borrados(moodle):
    print("get_alumnos_moodle_no_borrados(...)")
    """
    Devuelve una lista de alumnos (omite usuarios con username que empiece por prof) que actualmente están en moodle:
    #
    """
    cmd = "moosh -n user-list -n 50000 \"deleted = 0 and username not like 'prof%' \" " #listado de usuarios limitado a 50.000 # username (id), email,
    alumnos_moodle = run_moosh_command(moodle, cmd, True)
    
    alumnos = []    
    
    data_s = io.StringIO(alumnos_moodle).read()
    lines = data_s.splitlines()
    alumno = [
        {
            "username": line.split()[0],
            "userid": line.split()[1].replace("(","").replace("),",""),
            "email": line.split()[2].replace(",",""), # email del dominio google
            "email_sigad": "", # email de sigad
        }
        for line in lines
        # if line.split()[-1].endswith("moodle_1")
    ]
    alumnos.extend(alumno)

    # Recorro cada alumno y le añado el email de sigad
    for al in alumnos:
        
        command = '''\
            mysql --user=\"{DB_USER}\" --password=\"{DB_PASS}\" --host=\"{DB_HOST}\" -D \"{DB_NAME}\"  --execute=\"
                SELECT data
                FROM mdl_user_info_data
                where fieldid = 4 and userid = {id_usuario}
            \" | tail -n +2
            '''.format(DB_USER = DB_USER, DB_PASS = DB_PASS, DB_HOST = DB_HOST, DB_NAME = DB_NAME, id_usuario = al["userid"] )

        email_sigad = run_command( command , True).rstrip()
    
        print("email_sigad: ", email_sigad)

        al["email_sigad"] = email_sigad
    
    # Devuelvo el listado de alumnos que cumplen las condiciones
    return alumnos

def get_cursos(moodle):
    print("get_cursos(...)")
    """
    Devuelve una lista de los cursos que existen en moodle
    #
    """
    cmd = "moosh -n course-list | tail -n +2" 
    cursos_moodle = run_moosh_command(moodle, cmd, True)
    
    cursos = []    
    
    data_s = io.StringIO(cursos_moodle).read()
    lines = data_s.splitlines()
    curso = [
        {
            "courseid": line.split("\",\"")[0].replace("\"","").lstrip(),
            "category": line.split("\",\"")[1].rstrip(),
            "shortname": line.split("\",\"")[2].lstrip(),
            "fullname": line.split("\",\"")[3].rstrip(),
            "visible": line.split("\",\"")[4].replace("\"","").rstrip(),
        }
        for line in lines
        # if line.split()[-1].endswith("moodle_1")
    ]
    cursos.extend(curso)
    

    return cursos    

def procesaJsonEstudiantes(y, alumnos_sigad):
    """
    Procesa el fichero JSON obteniendo los alumnos y que estudian y los
    añade a alumnos_sigad
    """
    estudiantes=y["estudiantes"]
    # print( "type(estudiantes): ", type(estudiantes) ) # str
    estudiantesJson=json.loads(estudiantes)
    # print( "type(estudiantesJson: ",type(estudiantesJson) ) # dict

    fecha=estudiantesJson["fecha"]
    hora=estudiantesJson["hora"]
    alumnos=estudiantesJson["alumnos"]

    # print("fecha: " + str(fecha) + " y hora: " + str(hora) + " de creación del fichero")
    i = 0
    for alumno in alumnos:
        # print("i: ", i)
        # print("type(alumno): ", type(alumno) ) # dict
        idAlumno = alumno["idAlumno"]
        idTipoDocumento = alumno["idTipoDocumento"]
        documento = alumno["documento"]
        nombre = alumno["nombre"]
        apellido1 = alumno["apellido1"]
        apellido2 = alumno["apellido2"]
        emailSigad = alumno["email"] # este es el email de SIGAD
        centros = alumno["centros"]
        # print( "type(centros): ", type(centros) ) # list
        # print( "len(centros): ", len(centros) ) # 
        # creo el objeto
        miAlumno = Alumno(idAlumno, idTipoDocumento, documento, nombre, 
                apellido1, apellido2, emailSigad)
        # miAlumno.toText()
        #
        j=0
        for centro in centros:
            # print("  i: " + str(i) + ", j: " + str(j) + ", centro: " + str(centro) )
            # print("type(centro): ", type(centro) ) # dict

            codigoCentro = centro["codigoCentro"]
            centroo = centro["centro"]
            ciclos=centro["ciclos"]
            # print("ciclos: ", ciclos)
            # print("type(ciclos): ", type(ciclos) ) # str

            miCentro = Centro(codigoCentro, centroo)

            k = 0
            for ciclo in ciclos:
                # print("    i: ", i, ", j: ", j, ", k: ", k, ", ciclo: ", ciclo )
                # print("type(ciclo): ", type(ciclo) ) # dict
                
                idFicha = ciclo["idFicha"]
                codigoCiclo = ciclo["codigoCiclo"]
                cicloo = ciclo["ciclo"]
                siglasCiclo = ciclo["siglasCiclo"]
                modulos = ciclo["modulos"]

                miCiclo = Ciclo(idFicha, codigoCiclo, cicloo, siglasCiclo)

                l = 0
                for modulo in modulos:
                    #
                    idMateria = modulo["idMateria"]
                    moduloo = modulo["modulo"]
                    siglasModulo = modulo["siglasModulo"]
                    #
                    miModulo = Modulo(idMateria, moduloo, siglasModulo)
                    #
                    miCiclo.addModulo(miModulo)
                #
                miCentro.addCiclo(miCiclo)
            # Add miCentro to miAlumno
            miAlumno.addCentro(miCentro)
        # Add miAlumno to alumnos_sigad
        alumnos_sigad.append(miAlumno)
    #
    # End of procesaJsonEstudiantes
    #

def existeAlumnoEnMoodle(moodle, alumno):
    """
    Comprueba si el alumno dado existe en moodle
    Devuelve true si existe
    Devuelve false si no existe
    """
    print("existeAlumnoEnMoodle(...)")
    if alumno.getDocumento() is None:
        return False

    # moosh -n  user-list "username = 'estudiante1'"
    cmd = "moosh -n user-list \"username = '"+ alumno.getDocumento().lower() +"'\""
    
    username = run_moosh_command(moodle, cmd, True)

    if username == "" or "Error" in username:
        return False
    return True
    #
    # End of existeAlumnoEnMoodle
    #

def isAlumnoCreable(alumno):
    print("isAlumnoCreable(...)")
    alumno_creable = True
    if alumno.getEmailSigad() is None:
        print("El alumno a crear no tiene email sigad")
        alumno_creable = False
    if alumno.getNombre() is None:
        print("El alumno a crear no tiene nombre")
        alumno_creable = False
    if alumno.getApellidos() is None:
        print("El alumno a crear no tiene apellidos")
        alumno_creable = False
    if alumno.getDocumento() is None:
        print("El alumno a crear no tiene documento")
        alumno_creable = False

    return alumno_creable

def crearAlumnoEnMoodle(moodle, alumno, password):
    """
    Crea un usuario en moodle con los datos del objeto alumno
    Devuelve el id del alumno creado
    """
    print("crearAlumnoEnMoodle(...)")
    alumno_creable = isAlumnoCreable(alumno)

    if alumno_creable:
        cmd = "moosh -n user-create --password " + password + " --email " + alumno.getEmailDominio() \
            + " --digest 2 --city Aragón --country ES --firstname \"" +  alumno.getNombre() \
            + "\" --lastname \"" +  alumno.getApellidos() + "\" " \
            + alumno.getDocumento().lower()
        idUser = run_moosh_command(moodle, cmd, True).rstrip()

        print("idUser: '",idUser,"'")

        # Al usuario recién creado le añadimos el email de SIGAD en otros campos

        command = '''\
            mysql --user=\"{DB_USER}\" --password=\"{DB_PASS}\" --host=\"{DB_HOST}\" -D \"{DB_NAME}\"  --execute=\"
                insert into mdl_user_info_data (userid, fieldid, data) 
                values 
                ({idUser}, 4, '{email_sigad}')
            \"
            '''.format(DB_USER = DB_USER, DB_PASS = DB_PASS, DB_HOST = DB_HOST, DB_NAME = DB_NAME, idUser = idUser, email_sigad = alumno.getEmailSigad() )

        run_command( command, False )

        return idUser
    else:
        raise ValueError
    #
    # End of crearAlumnoEnMoodle
    #

def crearShortnameCurso(codigo_centro, siglas_ciclo, id_materia):
    """
    Crea el shortname del curso a partir de los datos dados teniendo en cuenta que hay que fusionar los cursos de Maite.
    """

    shortname = str(codigo_centro) + "-" + str(siglas_ciclo) + "-" + str(id_materia)

    # Casos especiales de fusión de cursos de Maite
    # TODO Borrar para antes de empezar el curso 2026-2027
    if shortname == "50020125-IFC301-5061" or shortname == "50020125-IFC302-5077" or shortname == "50020125-IFC303-5092" or shortname == "50020125-IFC201-5001":
        shortname = "50020125-IFC301-5061"

    return shortname
    #
    # End of crearShortnameCurso
    #

def es_nie_valido(nie: str) -> bool:
    """
    Devuelve True si el formato del string corresponde a un NIE válido.
    Formato: Letra inicial X, Y o Z + 7 dígitos + letra final (A-Z)
    """
    nie = nie.upper().strip()
    patron = r'^[XYZ]\d{7}[A-Z]$'
    return bool(re.match(patron, nie))

def es_dni_valido(dni: str) -> bool:
    """
    Devuelve True si el string tiene formato y letra de control válidos de un DNI español.
    Formato válido: 8 dígitos seguidos de una letra mayúscula (sin espacios ni guiones).
    """
    dni = dni.upper().strip()
    patron = r'^\d{8}[A-Z]$'
    return bool(re.match(patron, dni))

###################################################
###################################################
###################################################
# Lanzamos!
###################################################
###################################################
###################################################
try:
    main()
except Exception as exc:
    print("1.- traceback.print_exc()")
    traceback.print_exc()
    print("2.- traceback.print_exception(*sys.exc_info())")
    traceback.print_exception(*sys.exc_info())
    print("--------------------")
    print(exc)

    plantilla_path = Path("/var/fp-distancia-gestion-usuarios-automatica/templates/haFalladoElInforme.html")
    plantilla = plantilla_path.read_text(encoding="utf-8")

    mensaje = plantilla.format(
        subdomain = SUBDOMAIN,
        filename_md = filename_md,
        filename_csv = filename_csv,
        error = str(exc),
        traceback = str(traceback.print_exc()),
        tracebackException = str(traceback.print_exception(*sys.exc_info())),
    )

    emails = REPORT_TO.split()
    for email in emails:
        send_email_con_adjuntos("gestion@fpvirtualaragon.es", "ERROR - Informe automatizado gestión automática usuarios moodle", mensaje, [filename_md, filename_csv] )
