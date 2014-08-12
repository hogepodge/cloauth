import poauth
import os
import document
import zipfile
import StringIO
import tempfile
import hashlib
import pdb
import common
import gpsobject
import dicomobject
from lxml import etree
import shutil

def brainkfiles(bkstub) :
    """ returns tuple (bkfullfiles,bkfiles) of all files corresponding
to braink stub.  bkfullfiles has full path, bkfiles does not have full
path (i.e. directory not prepended)"""
    try :
        bkstub_curr=os.path.expanduser(bkstub)
        (bkhead,bktail)=os.path.split(bkstub_curr)
        bkfiles = [f for f in os.listdir(bkhead) if f.startswith(bktail+'.')]
        bkfullfiles =  [os.sep.join([bkhead,f]) for f in bkfiles]
    except OSError :
        bkfiles=[]
        bkfullfiles=[]        
    return (bkfullfiles,bkfiles)

def isvalidbkstub(bkstub) :
    """ checks that X.Parameters.txt is one of the braink files"""
    (bkfullfiles,bkfiles)=brainkfiles(bkstub)
    return True in [f.endswith('.Parameters.txt') for f in bkfiles]
    
def brainkhash(bkstub) :
    bkfullfiles=brainkfiles(bkstub)[0]
    # do not include Paramters.txt in hash : needed as I wish to be able to relocate
    # braink files, which will involve changing paths to parent data in parameters.txt,
    # this should not affect id used to determine if a given braink data set is in database
    bkfullfiles=[f for f in bkfullfiles if not f.endswith('.Parameters.txt')]

    sorted_bkfiles=sorted(bkfullfiles)
    m=hashlib.md5()
    blocksize = 65536
    for f in sorted_bkfiles :
        fid=open(f)
        buf=fid.read(blocksize)
        while(len(buf)>0) :
            m.update(buf)
            buf=fid.read(blocksize)
        fid.close()
    return m.hexdigest()

def _md5_stream(stream):
        blocksize = 65536
        buf = stream.read(blocksize)
        m = hashlib.md5()
        while len(buf) > 0:
            m.update(buf)
            buf = stream.read(blocksize)
        return m.hexdigest()
    
def zipbkstub(bkstub,zipfilename) :
    bkstub=os.path.expanduser(bkstub)
    (bkhead,bktail)=os.path.split(bkstub)
    zfile = zipfile.ZipFile(zipfilename, 'w', zipfile.ZIP_DEFLATED)
    (bkfullfiles,bkfiles)=brainkfiles(bkstub)
    for f in bkfiles :
        zfile.write(filename=os.sep.join([bkhead,f]),
                    arcname=f.replace(bktail,'BRAINK') )
    zfile.close()
    return zfile

def parsebkstub(bkstub) :
    bkparam={}
    if isvalidbkstub(bkstub) :
        parameterlines=open(bkstub+'.Parameters.txt','r').readlines()
        # first line has form : N versionstring seriesID
        try :
            tmp=parameterlines[0].split()
            bkparam['bkversion'] = tmp[1]
            bkparam['seriesID'] = tmp[2]
        except IndexError :
            pass

        for line in parameterlines[1:] :
            tmp=line.split()
            bkparam[tmp[0]]=tmp[1:]

    return bkparam

def brainkdocument(bkstub,parentdataids,zipfile) :
    bkparam=parsebkstub(bkstub)
    brainkdoc=document.DocumentPrototype()
    brainkdoc.set_derived()
    brainkdoc.set_file(zipfile)
    brainkdoc.set_datasource('BrainK',bkparam['bkversion'])
    brainkdoc.add_datasource_meta('brainkhash',brainkhash(bkstub))
    # parentdataids should contain database ids, if the parent data has been checked in
    # Intention is for it to contain fields
    # parentdataids['MRI']
    # parentdataids['CT']
    # parentdataids['GPS']
    if 'MRI' not in parentdataids :
        raise Exception('braink must have at least MRI parent defined')

    for key in parentdataids :
        brainkdoc.add_parentdata(key,parentdataids[key])

    [bkfullfiles,bkfiles]=brainkfiles(bkstub)
    for f in bkfullfiles :
        brainkdoc.add_artifact(key="braink",filename=f)

    return brainkdoc

def checkbrainkexistence(server,token,bkhash) :
    querystring = ''.join([server, "/object.xml?key=brainkhash&value=", bkhash])
    documentlist = common.checkexistence(server,token,querystring)
    if len(documentlist) == 0:
        return None
    else: 
        return documentlist[0]

#def replace_from_right(source,findstg,replacestg,count):
#    """ replace count occurences of findstg with replacestg, but counted from right, not left"""
#    isource =source[::-1]
#    ifindstg=findstg[::-1]
#    ireplacestg=replacestg[::-1]
#    return isource.replace(ifindstg,ireplacestg,count)[::-1]
    
def uploadbraink(server,token,bkstub,recursive_checkin=False):
    """ compute hash, check against server, if not found, create zipfile and upload"""
    if not isvalidbkstub(bkstub) :
        raise Exception('invalid brainkstub')

    bkhash=brainkhash(bkstub)

    common.lout('Asked to upload braink with stub '+bkstub+' bkhash '+bkhash+'\n')

    # how to handle recursive_checkin if MRI,CT,GPS objects do not define subject?
    # Grab subject id from MRI, if possible
    #
    # As of now, code will give not succesfully infer subject if MRI
    # is not in the database and if it is not a DICOM file.
    #
    # It is possible that CT could be dicom, and subject could be
    # inferred from CT, but I won't bother to handle this case. To be
    # able to deal with this case, the user would need to check in the
    # non-DICOM MRI with some tool that associates a subject id.
    
    braink_server_xml=checkbrainkexistence(server,token,bkhash)
    if not braink_server_xml is None :
        common.lout('braink with hash '+bkhash+' found on server, not uploading\n')
        return braink_server_xml
    else :
        # need to upload 
        common.lout('braink with hash '+bkhash+' not found on server, uploading\n')
        bkparam=parsebkstub(bkstub)
        parentdataids={}
        subject_id = None
        
        if 'MRI_file' in bkparam :
            mri_path = bkparam['MRI_file'][1]
            mri_parsed_xml = common.get_database_xml_from_path(server,token,mri_path)

            if mri_parsed_xml is None :
                if recursive_checkin :
                    # todo : this should be upload_path, not uploaddicom
                    # mri image may not be a dicom directory
                    mri_parsed_xml = dicomobject.upload_image_from_path(server,token,mri_path)
                    if mri_parsed_xml is None :
                        raise Exception('Failed to check in image '+mri_path)                    
                else :
                    raise Exception('MRI at path '+mri_path+' not in database : should check it in')

            mri_id = common.get_id_from_parsed_xml(mri_parsed_xml)
            subject_id = common.get_parents_from_parsed_xml(mri_parsed_xml)[0]
            parentdataids['MRI']=mri_id
                
        if 'CT_file' in bkparam :
            ct_path = bkparam['CT_file'][1]
            ct_parsed_xml= common.get_database_xml_from_path(server,token,ct_path)
            if ct_id is None :
                if recursive_checkin :
                    ct_parsed_xml=dicomobject.upload_image_from_path(server,token,ct_path,parent_id=subject_id)
                else:
                    raise Exception('CT at path '+ct_path+' not in database : should check it in')
            ct_id=common.get_id_from_parsed_xml(ct_parsed_xml)
            parentdataids['CT']=ct_id
            
        # I have seen parameters of form GPS_sensor_file_(CT_2_MRI),
        # I will assume I can find a single key that starts with GPS_sensor_file
        GPS_key = [x for x in bkparam.keys() if x.startswith('GPS_sensor_file') and len(bkparam[x])==2]
        if len(GPS_key)>1 :
            raise Exception('Unexpected number of GPS_sensor_file parameters found')
        if len(GPS_key)>0 :
            gps_path = bkparam[GPS_key[0]][1]
            gps_parsed_xml = common.get_database_xml_from_path(server,token,gps_path)
            if gps_parsed_xml is None :
                if recursive_checkin :
                    gps_parsed_xml=gpsobject.uploadgps(server,token,gps_path,subject_id=subject_id)
                else :
                    raise Exception('GPS at path '+gps_path+' not in database : should check it in')
            gps_id=common.get_id_from_parsed_xml(gps_parsed_xml)
            parentdataids['GPS']=gps_id
        
        # todo :   
        # similar code for CT_file, GPS_file (or whatever they get called by BrainK)
        tmpdname=tempfile.mkdtemp()
        bkhead,bktail=os.path.split(bkstub)
        zipfilename = os.sep.join([tmpdname,bktail+'-bkout.zip'])
        try :
            print 'creating braink zipfile',
            zfile=zipbkstub(bkstub,zipfilename)
            print
            brainkdoc=brainkdocument(bkstub,parentdataids,zipfilename)
            client=poauth.OAuthClient(token)
            response=client.post(server+'/object.xml',
                             data={'object':brainkdoc.toxml()},
                             files={'file': open(zfile.filename,'rb')} )
            #return etree.fromstring(response.text)
            return common.parse_xml_from_server(response.text)
        finally :
            shutil.rmtree(tmpdname,ignore_errors=True)
    

        

# create zipfile for braink object
# create xml for braink object

# upload routine : should check on server that parent exists, what to do if it does not?
# how to handle parents that are not dicom data, but some sort of other raw file data?
#
# I want braink parameters to include file paths for all its inputs : MR, CT, GPS, whatever else
# Then, I can analyze each such path to be able to tell if that object is stored in database
# (uid if it is DICOM, otherwise md5 hash of file)
#
# To check this data back out, though, it would be very useful if
# braink was modified to avoid its convention of basing the input GPS
# and CT filenames from the MRI file path.  I may even want to change
# the parameters.txt file on checkout, to have freedom to install data
# somewhere else.



# create zipfile
if __name__=='__main__' :


    token_xml_filename='/Users/hammond/metaprop/rest_credential_token.xml'

    ## try :
    ##     token_xml = lxml.etree.parse( open(token_xml_filename) )
    ##     identifier= token_xml.findall('mac-key-identifier')[0].text
    ##     key = token_xml.findall('mac-key')[0].text
    ##     issue_time=token_xml.findall('issue-time')[0].text
    ##     # temporarily hard-code server url
    ##     server='http://localhost:3604' 
    ##     token=poauth.Credentials(identifier=identifier,
    ##                          key=key,
    ##                          issue_time=int(issue_time) )
    ## except Exception as e :
    ##     print 'Could not load token from file '+token_xml_filename
    ##     raise(e)

    (server,token)=common.load_credential_token_from_xml(token_xml_filename)
    bkstub='~/metaprop/EGI_101/t1'
    bkstub=os.path.expanduser(bkstub)
    uploadbraink(server,token,bkstub)
    #bkstub=os.path.expanduser(bkstub)




    ## if isvalidbkstub(bkstub):
    ##     bkfullfiles,bkfiles=brainkfiles(bkstub)
    ##     bkhead,bktail=os.path.split(bkstub)
    ##     print 'hash : ' , brainkhash(bkstub)

    ##     # try to find parent ids
    ##     bkparam=parsebkstub(bkstub)
    ##     parentdataids={}
    ##     if 'MRI_file' in bkparam :
    ##         mri_path = bkparam['MRI_file'][1]
    ##         mri_id = common.get_database_id_from_path(server,token,mri_path)
    ##         if mri_id is None :
    ##             raise Exception('MRI not in database : should check it in')
    ##         else :
    ##             parentdataids['MRI']=mri_id
    ##     # todo :   
    ##     # similar code for CT_file, GPS_file (or whatever they get called by BrainK)

    ##     # check if it exists on server
    ##     bkhash=brainkhash(bkstub)
    ##     server_bkdoc=checkbrainkexistence(server,token,bkhash)
    ##     if not server_bkdoc is None :
    ##         print 'BrainK found on server : returned xml below'
    ##         print lxml.etree.tostring(server_bkdoc)
    ##     else :
    ##         print 'BrainK not found on server : uploading'
        
    ##         tmpdname=tempfile.mkdtemp()
    ##         tmpfname = os.sep.join([tmpdname,bktail+'-bkout.zip'])
    ##         zipfilename=tmpfname
    ##         zfile=zipbkstub(bkstub,zipfilename)
    ##         brainkdoc=brainkdocument(bkstub,parentdataids,zipfilename)

    ##         client=poauth.OAuthClient(token)
    ##         response=client.post(server+'/object',
    ##                         data={'object':brainkdoc.toxml()},
    ##                         files={'file': open(zfile.filename,'rb')} )
    ##         print '--- uploaded this xml file --- '
    ##         print brainkdoc.toxml()
    ##         print '---  --- '

    ##         print response.text
        

    ##     # clean up temporary directory
    ##     try :
    ##         os.remove(tmpfname)
    ##         os.rmdir(tmpdname)
    ##     except (OSError, NameError) :
    ##         pass
