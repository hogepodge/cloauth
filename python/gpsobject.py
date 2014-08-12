import common
import document
import tempfile
import poauth
import os
import shutil
import zipfile
from lxml import etree

# below could go in file called gpsobject
def gpsdocument(gps_path,subject_id,zipfile) :
    gpsdoc=document.DocumentPrototype()
    gpsdoc.set_derived()
    gpsdoc.set_file(zipfile)
    gpsdoc.add_parentdata('Subject',subject_id)
    gpsdoc.set_datasource('GPS','raw')
    # todo : further analyze GPS file to extract other data
    gpsdoc.add_artifact(key='gps',filename=gps_path)
    gpshash=common.rawfilehash(gps_path)
    gpsdoc.add_datasource_meta('gpshash',gpshash)
    return gpsdoc

def checkgpsexistence(server,token,gpshash):
    querystring = ''.join([server, "/object.xml?key=gpshash&value=", gpshash])
    documentlist = common.checkexistence(server,token,querystring)
    if len(documentlist) == 0:
        return None
    else: 
        return documentlist[0]

def uploadgps(server,token,gps_path,subject_id) :
    common.lout('Asked to upload gps with path '+gps_path+' and parent '+subject_id +'\n')
    if not os.path.isfile(gps_path) :
        raise Exception('Invalid GPS path '+gps_path+ ' given')

    gpshash=common.rawfilehash(gps_path)
    gps_parsed_xml=checkgpsexistence(server,token,gpshash)
    if not gps_parsed_xml is None :
        common.lout('gps with path '+gps_path+' in database, not uploading\n')
        return gps_parsed_xml
    else :
        common.lout('gps with path '+gps_path+' not in database, uploading\n')
        try :
            tmpdname=tempfile.mkdtemp()
            zipfilename = os.sep.join([tmpdname,'gps.zip'])
            zfile = zipfile.ZipFile(zipfilename, 'w', zipfile.ZIP_DEFLATED)
            zfile.write(filename=gps_path,arcname=os.path.basename(gps_path))
            zfile.close()
            gpsdoc=gpsdocument(gps_path,subject_id,zfile.filename)
            client=poauth.OAuthClient(token)
            response=client.post(server+'/object.xml',
                             data={'object':gpsdoc.toxml()},
                             files={'file': open(zfile.filename,'rb')} )
            return common.parse_xml_from_server(response.text)
        finally:
            shutil.rmtree(tmpdname,ignore_errors=True)
