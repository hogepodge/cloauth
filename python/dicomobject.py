import pdb
import shutil
import dicom
import poauth
import os.path
import os
import document
import zipfile
import copy
import StringIO
import tempfile
import common
from lxml import etree

class NamedStringIO(StringIO.StringIO):
    def __init__(self, name, string=None):
        StringIO.StringIO.__init__(self, string)
        self.name = name

class CheckDicomException(Exception):
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return self.msg

class DicomSubject:
    def __init__(self, dicom_file):
        self.name = dicom_file.PatientName

        gender = dicom_file.PatientSex
        if gender == 'M':
            self.gender = 'MALE'
        else:
            self.gender = 'FEMALE'

        dob = dicom_file.PatientBirthDate
        self.dob = ''.join([dob[0:4], '-', dob[4:6], '-', dob[6:8]])
        self.age = dicom_file.PatientAge
        self.weight = dicom_file.PatientWeight

        self.document = document.DocumentPrototype()
        self.document.set_datasource('Subject', '1')
        self.document.add_datasource_meta('name', self.name)
        self.document.add_datasource_meta('gender', self.gender)
#        self.document.add_datasource_meta('egi_id', '')
        self.document.add_datasource_meta('dob', self.dob)
        self.document.add_datasource_meta('age', self.age)
        self.document.add_datasource_meta('weight', str(self.weight))
        self.document.set_primary()
        self.filename = ''.join([self.name, '.xml'])
        content = NamedStringIO(self.filename, self.toxml())
        self.document.set_file_stream(self.filename, content)

    def toxml(self):
        xmldoc = etree.Element('subject')
        name = etree.SubElement(xmldoc, 'name')
        name.text = self.name
        gender = etree.SubElement(xmldoc, 'gender')
        gender.text = self.gender
        egi_id = etree.SubElement(xmldoc, 'egi_id')
        egi_id.text = ''
        dob = etree.SubElement(xmldoc, 'dob')
        dob.text = self.dob
        age = etree.SubElement(xmldoc, 'age')
        age.text = self.age
        weight = etree.SubElement(xmldoc, 'weight')
        weight.text = str(self.weight)

        return etree.tostring(xmldoc, pretty_print=True)


def dicomdocument(dicom_dir,subject_id,zipfile) :
    """ zipfile should be zipped from dicom_dir, dicom_dir should be
    valid (not checked here), subject_id should be id of subject
    referred to by this dicom file """
    df=getfirstdicomfile(dicom_dir)

    description = df.SeriesDescription
    series_date = df.SeriesDate
    series_date = ''.join([series_date[0:4], '-', series_date[4:6], '-', series_date[6:8]])
    series_time = df.SeriesTime
    series_time = ''.join([series_time[0:2], ':', series_time[2:4], ':', series_time[4:6]])
    local_subject_id = df.PatientName
    institution_name = df.InstitutionName
    institution_address = df.InstitutionAddress
    sop_class_uid = repr(df.SOPClassUID).strip("'")
    series_instance_uid =df.SeriesInstanceUID
    study_instance_uid =df.StudyInstanceUID
    sop_class = df.SOPClassUID.name

    dicomdoc = document.DocumentPrototype()
    dicomdoc.set_derived()
    dicomdoc.set_file(zipfile)
    dicomdoc.set_datasource('DICOM', institution_name)
    dicomdoc.add_datasource_meta('description', description)

    #dicomdoc.add_datasource_meta('numimages', num_images)
    dicomdoc.add_datasource_meta('series-date', series_date)
    dicomdoc.add_datasource_meta('series-time', series_time)
    dicomdoc.add_datasource_meta('parent-name', series_instance_uid)
    dicomdoc.add_datasource_meta('local-subject-id', local_subject_id)
    dicomdoc.add_datasource_meta('institution-name', institution_name)
    dicomdoc.add_datasource_meta('institution-address', institution_address)
    dicomdoc.add_datasource_meta('sop-class-uid', sop_class_uid)
    dicomdoc.add_datasource_meta('series-instance-uid', series_instance_uid)
    dicomdoc.add_datasource_meta('study-instance-uid', study_instance_uid)
    dicomdoc.add_datasource_meta('sop-class', sop_class)

    dicomdoc.add_parentdata('Subject', subject_id)

    # get hashes of all artifacts (the dicom files)
    for fullfile in [os.sep.join([dicom_dir,f]) for f in os.listdir(dicom_dir)]:
        dicomdoc.add_artifact(key="dcm",filename=fullfile)

    return dicomdoc

def getfirstdicomfile(dicom_directory):
    """ Assuming dicom directory
    is valid, load the first file in the directory with
    dicom.read_file, and return it"""

    fname=os.sep.join([dicom_directory,os.listdir(dicom_directory)[0]])
    return dicom.read_file(fname)
    
def isvaliddicom(dicom_directory):
    try :
        dicompath = os.path.abspath(dicom_directory)
        if not os.path.exists(dicompath):
            raise CheckDicomException("path to dicom directory does not exist")
        if not os.path.isdir(dicom_directory):
            raise CheckDicomException("path to dicom directory is not a directory")
        head_file = None
        sop_class_uid_global = None
        series_instance_uid_global = None
        study_instance_uid_global = None
        num_images = 0
        for dicom_file_name in [os.sep.join([dicom_directory,f]) for f in os.listdir(dicom_directory)]:
            num_images = num_images + 1
            # Walk the files to make sure they're all really dicom files
            # Want a flat directory
            if os.path.isdir(dicom_file_name):
                raise CheckDicomException("subfile is a directory. only dicom images allowed")
            # Read the dicom file. Will raise if this fails
            dicom_file = dicom.read_file(dicom_file_name)
            # Get the basic identifiers of this type to verify consistency
            sop_class_uid = dicom_file.SOPClassUID
            series_instance_uid = dicom_file.SeriesInstanceUID
            study_instance_uid = dicom_file.StudyInstanceUID
            # First file read should set the 'global' variables to check consistency
            if (sop_class_uid_global == None and
                series_instance_uid_global == None and
                study_instance_uid_global == None and
                head_file == None): 
               sop_class_uid_global = sop_class_uid
               series_instance_uid_global = series_instance_uid
               study_instance_uid_global = study_instance_uid
               head_file = dicom_file
        # test the identifiers for consistency
            if sop_class_uid_global != sop_class_uid:
                raise CheckDicomException("sop_class_uid inconsistency in files")
            if series_instance_uid_global != series_instance_uid:
                raise CheckDicomException("series_instance_uid inconsistency in files")
            if study_instance_uid_global != study_instance_uid:
                raise CheckDicomException("study_instance_uid_global inconsistency in files")
        return True
    except Exception as e :
        print repr(e)
        return False

def zipdicom(dicom_directory,zipfilename) :
    """
Check that dicom_directory is valid, then zip it into provided
zipfilename.

Returns zipfile object, and a single loaded dicom_file (first in
directory) for later extraction of subject information
"""
    
    # Below does not catch exceptions, so code will just stop if dicom_directory
    # invalid. Perhaps this should be fixed later.
    if isvaliddicom(dicom_directory) :
        zfile = zipfile.ZipFile(zipfilename, 'w', zipfile.ZIP_DEFLATED)
        rootlen = len(dicom_directory) + 1
        dicom_file=False
        for base, dirs, files in os.walk(dicom_directory):
            for f in files:
                fn = os.path.join(dicom_directory, f)
                zfile.write(fn, fn[rootlen:])
                # Read a single dicom file. This is safe, as we have
                # already verified that all files are consistent, for
                # the same subject and scan
                if not dicom_file :
                    dicom_file=dicom.read_file(fn)

        zfile.close()

    return zfile, dicom_file


def checksubjectexistence(server, token, subject):
    querystring = ''.join(
            [server, 
             "/object.xml?key=name&value=",
             subject.name])
    subjectlist = common.checkexistence(server, token, querystring)
    if len(subjectlist) == 0:
        return None
    else:
        return subjectlist[0]

def checkdicomexistence(server,token,uid):
    querystring = ''.join([server, "/object.xml?key=series-instance-uid&value=", uid])
    documentlist = common.checkexistence(server,token,querystring)
    if len(documentlist) == 0:
        return None
    else: 
        return documentlist[0]

def uploadsubject(server, token, subject):
    common.lout('Asked to upload subject with name '+subject.name+'\n')
    subject_parsed_xml=checksubjectexistence(server,token,subject)
    if subject_parsed_xml is None :
        common.lout('Subject with name '+subject.name+' not in database, uploading\n')
        client = poauth.OAuthClient(token)
        memoryfile = NamedStringIO(subject.filename, subject.toxml())

        response = client.post(''.join([server, '/object.xml']),
                               data={"object": subject.document.toxml()},
                               files={"file": memoryfile})


        memoryfile.close()
        subject_parsed_xml=common.parse_xml_from_server(response.text)
    else :
        common.lout('Subject with name '+subject.name+' in database, not uploading\n')

    return subject_parsed_xml

def uploaddicom(server, token, dicom_directory):
    """
Create zip archive of dicom files, upload to server. This will check if subject is in server, upload it if not.
Returns parsed xml for dicom object on server. If called on dicom already in server, will return same object as checkdicomexistence.
"""
    common.lout('Asked to upload dicom with path '+dicom_directory+' \n')
    dicom_image=getfirstdicomfile(dicom_directory)
    subject = DicomSubject(dicom_image)
    dicom_parsed_xml = checkdicomexistence(server, token, dicom_image.SeriesInstanceUID)
    subject_parsed_xml =uploadsubject(server, token, subject)
    subject_id = common.get_id_from_parsed_xml(subject_parsed_xml)
    
    if dicom_parsed_xml == None:
        common.lout('DICOM with path '+dicom_directory+' not in database, uploading\n')
        try :
            tmpdname=tempfile.mkdtemp()
            dicom_directory_base=os.path.basename(os.path.normpath(dicom_directory))
            tmpfname = os.sep.join([tmpdname,dicom_directory_base+'.zip'])
            zipfile, dicom_image = zipdicom(dicom_directory,tmpfname)
            # so, now, actually do checkin      
            dicom_doc=dicomdocument(dicom_directory,subject_id,zipfile.filename)
            client=poauth.OAuthClient(token)
            response=client.post(server+'/object.xml',
                                data={'object':dicom_doc.toxml()},
                                files={'file': open(zipfile.filename,'rb')} )
            dicom_parsed_xml=common.parse_xml_from_server(response.text)
        except Exception as e :
            print(e.__repr__())
        finally :
            shutil.rmtree(tmpdname,ignore_errors=True)
    else:
        common.lout('DICOM with path '+dicom_directory+' in database, not uploading\n')
    return dicom_parsed_xml

def upload_image_from_path(server,token,image_path,subject_id=None) :
    """path may be dicom, nii, or other type of path. If it is DICOM and no
subject is specified, infer subject"""

    obj_xml=None
    if os.path.isfile(image_path) :
        # special case each supported image type
        ft=common.determine_file_type(image_path)
        if ft == 'nii' :
            obj_xml=niiobject.uploadnii(server,token,image_path,parent_id=subject_id)
        else :
            print 'Warning : cannot upload image ' + image_path
    
    if os.path.isdir(image_path) :
        if isvaliddicom(image_path) :
            if not subject_id is None :
                print 'Warning : subject_id passed when using upload_image_from_path with DICOM image'
            obj_xml=uploaddicom(server,token,image_path)
    
    return obj_xml
    #    raise Exception('Images other than DICOM not supported yet')


    
if __name__=='__main__':
    #checkdicom("foo")
    token = poauth.Credentials('7020b02d-5240-41d8-981d-ce2faf0115a8',
            '08712e33-e62b-4a39-85e7-e2bb64dad2cb',
            1357856519246)
    print(uploaddicom("http://prodigal.nic.uoregon.edu:3604", token, "112_0001438_252645"))
