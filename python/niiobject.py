import tempfile
import os
import shutil
import zipfile
from lxml import etree
import nibabel

import poauth
import dicomobject
import common
import document

def checkniiexistence(server,token,niihash):
    querystring = ''.join([server, "/object.xml?key=niihash&value=", niihash])
    documentlist = common.checkexistence(server,token,querystring)
    if len(documentlist) == 0:
        return None
    else: 
        return documentlist[0]
    pass

def niidocument(nii_path,subject_id,zipfile):
    niidoc=document.DocumentPrototype()
    niidoc.set_derived()
    niidoc.set_file(zipfile)
    niidoc.add_parentdata('Subject',subject_id)
    niidoc.set_datasource('NII','Nifti Image')
    niidoc.add_datasource_meta('niihash',niihash(nii_path))
    img = nibabel.load(nii_path)
    descrip=str(img.get_header().get('descrip'))

    # don't add descrip as metadata if it is blank :
    # adding blank fields to xml annoyed server
    if descrip.strip() != '' :
        niidoc.add_datasource_meta('descrip',descrip)

    niidoc.add_artifact(key='nii',filename=nii_path)
    
    return niidoc

def zipnii(nii_path,zipfilename):
    zfile=zipfile.ZipFile(zipfilename,'w',zipfile.ZIP_DEFLATED)
    zfile.write(filename=nii_path,arcname=os.path.basename(nii_path))
    zfile.close()
    return zfile

def niihash(nii_path):
    return common.rawfilehash(nii_path)
    pass

def uploadnii(server,token,nii_path,subject_id) :

    # subject_id may be none : in this case, succeed only if nii already in database
    common.lout('Asked to upload nii with path '+nii_path+' and parent '+str(subject_id) +'\n')
    if not common.determine_file_type(nii_path)=='nii' :
        raise Exception('Invalid nii path '+nii_path+' given')
    niihashvalue=niihash(nii_path)
    nii_parsed_xml=checkniiexistence(server,token,niihashvalue)
    if not nii_parsed_xml is None :
        common.lout('nii with path '+nii_path+' in database, not uploading')
        return nii_parsed_xml
    else :
        common.lout('nii with path '+nii_path+' not in database, uploading')
        try :
            tmpdname=tempfile.mkdtemp()
            zipfilename=os.sep.join([tmpdname,'nii.zip'])
            zfile=zipnii(nii_path,zipfilename)
            niidoc=niidocument(nii_path,subject_id,zfile.filename)
            client=poauth.OAuthClient(token)
            response=client.post(server+'/object.xml',
                                 data={'object':niidoc.toxml()},
                                 files={'file': open(zfile.filename,'rb')} )
            return common.parse_xml_from_server(response.text)
          
        finally:
            shutil.rmtree(tmpdname,ignore_errors=True)


def upload_nii_with_dicom_reference(server,token,nii_path,reference_dicom_path) :
    """ Extract subject from dicom, upload nii file using this
    subject. Use with care! This routine cannot verify that the nii
    and dicom actually correspond"""   
    if not dicomobject.isvaliddicom(reference_dicom_path) :
        raise Exception('Invalid dicom path ' +reference_dicom_path+' given')

    subject=dicomobject.DicomSubject(dicomobject.getfirstdicomfile(reference_dicom_path))
    # this will add subject to database, if it isn't there already
    subject_parsed_xml=dicomobject.uploadsubject(server,token,subject)
    subject_id=common.get_id_from_parsed_xml(subject_parsed_xml)
    nii_parsed_xml=uploadnii(server,token,nii_path,subject_id)
    return nii_parsed_xml
