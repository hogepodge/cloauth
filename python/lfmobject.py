import document
import common
import pdb
import os
import hashlib
import poauth
from lxml import etree
import shutil
import tempfile
import zipfile


# this should go in base class
class ParentNotFoundException(Exception) :
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return self.msg


# checkin for lead-field matrix
def checklfmexistence(server,token, lfm_hdr_path ,lfmhashval=''):
    if lfmhashval=='' :
        lfmhashval=lfmhash(lfm_hdr_path)
    return checkkeyvalueexistence(server,token,key='lfmhash',value=lfmhashval)
    
# this should go in base class
def checkkeyvalueexistence(server,token,key,value) :
    """ Given key/value pair, query server and return first of
    returned parsed xml objects, or None if there is no match"""

    query = server+'/object.xml?key='+key+'&value='+value
    client = poauth.OAuthClient(token)
    response = client.get(query)
    if response.status_code != 200:
        raise Exception("Bad server response. Expected 200. Got %s" % (response.status_code))

    documentlist = None 
    try:
        documentlist = etree.fromstring(response.text)
    except Exception as e :
        # magic number : 38 (removes instance encoding string)
        documentlist = etree.fromstring(response.text[38:])
    if documentlist.tag != "objects":
        raise Exception('Expected a list of objects from the server.')

    if len(documentlist) == 0:
        return None
    else: 
        return documentlist[0]

def lfmdocument(lfm_hdr_path,braink_id,zipfile):
    lfmdoc=document.DocumentPrototype()
    lfmdoc.set_derived()
    lfmdoc.set_file(zipfile)
    lfmdoc.set_datasource('LFM','unknown_version')

    lfmdoc.add_datasource_meta('lfmhash',lfmhash(lfm_hdr_path) )

    # put in all parameters from lfm header
    D=parselfmheader(lfm_hdr_path)
    for key in D :
        lfmdoc.add_datasource_meta(key,D[key])

    lfmdoc.add_parentdata('BrainK',braink_id)

    lfmdir=os.path.dirname(lfm_hdr_path)
    for f in os.listdir(lfmdir) :
        fullfile=os.sep.join([lfmdir,f])
        try :
            ext=f.split('.')[-1]
        except Exception as e:
            ext='unknown'
        lfmdoc.add_artifact(key=ext,filename=fullfile)
        
    return lfmdoc
    
# this should be in common, or base class once I refactor
def zip_directory(dirname,zipfilename) :
    zfile=zipfile.ZipFile(zipfilename,'w',zipfile.ZIP_DEFLATED)
    for f in os.listdir(dirname) :
        fullfile = os.sep.join([dirname,f])
        zfile.write(filename=fullfile,arcname=f)
    zfile.close()
    return zfile

# this should go in base class
def hash_file_list(file_list) :    
    m=hashlib.md5()
    blocksize = 65536
    for f in file_list :
        fid=open(f)
        buf=fid.read(blocksize)
        while(len(buf)>0) :
            m.update(buf)
            buf=fid.read(blocksize)
        fid.close()
    return m.hexdigest()

def ziplfm(lfm_hdr_path,zipfilename) :
    lfmdir=os.path.dirname(lfm_hdr_path)
    zfile = zip_directory(lfmdir,zipfilename)
    return zfile
    
def lfmhash(lfm_hdr_path) :
    lfmdir=os.path.dirname(lfm_hdr_path)
    fullfiles=[os.sep.join([lfmdir,f]) for f in os.listdir(lfmdir)]
    return hash_file_list( sorted(fullfiles) )

def find_parent_braink(server,token,lfm_hdr_path) :
    parent_bk_files=['dipolesFileName1','dipolesFileName2','geometryFileName','normalsFileName','sensorsFileName']

    parsed_lfmhdr=parselfmheader(lfm_hdr_path)
    idsets=[]
    for p in parent_bk_files :
        bkhash=common.rawfilehash(parsed_lfmhdr[p])
        # now search on these tags ... how to do it ?
        # print bkhash
        querystring = ''.join(
            [server, 
             "/object.xml?key=artifacthash&value=",
             bkhash])
        idlist_curr=[common.get_id_from_parsed_xml(xml) for xml in
                     common.checkexistence(server, token, querystring) ]
        idsets.append( frozenset(idlist_curr) )
    # If I understand correctly, calling reduce with intersection
    # function on list of sets computes intersection of all the sets
    intersect_ids=reduce(frozenset.intersection,idsets)
    if len(intersect_ids)==0 :
        return None
    if len(intersect_ids)>1 :
        print 'Warning : multiple matching BrainK objects found : '
        for id in intersect_ids :
            print id
    return list(intersect_ids)[0]

def _uploadzipfile(server,token,doc,zipfile) :
    client=poauth.OAuthClient(token)
    response=client.post(server+'/object.xml',
                         data={'object':doc.toxml()},
                         files={'file': open(zipfile.filename,'rb')} )
    return common.parse_xml_from_server(response.text)
 
def uploadlfm(server,token,lfm_hdr_path):
    lfmhashval=lfmhash(lfm_hdr_path)
    common.lout('Asked to upload lfm with lfmhash '+lfmhashval+'\n')
    lfm_parsed_xml=checklfmexistence(server,token,lfm_hdr_path,lfmhashval)

    if lfm_parsed_xml is None :
        common.lout('lfm with hash ' + lfmhashval+' not in database, uploading\n')
        braink_id=find_parent_braink(server,token,lfm_hdr_path) 
        if braink_id is None :
            raise ParentNotFoundException('Parent BrainK run not found on server - you should check it in\n')
        try :
            tmpdname=tempfile.mkdtemp()
            tmpfname = os.sep.join([tmpdname,'lfm.zip'])
            zipfile=ziplfm(lfm_hdr_path,tmpfname)
            lfmdoc=lfmdocument(lfm_hdr_path,braink_id,zipfile.filename)
            lfm_parsed_xml=_uploadzipfile(server,token,lfmdoc,zipfile)
        ## except Exception as e :
        ##     print e
        finally :
            shutil.rmtree(tmpdname,ignore_errors=True)
    else:
        common.lout('lfm with hash ' + lfmhashval+' in database, not uploading\n')

    return lfm_parsed_xml

def parselfmheader(lfm_hdr_path) :
    D={}
    hdrlines=open(lfm_hdr_path).readlines()
    hdrlines=[x for x in hdrlines if not x.startswith('====')]
    hdrlines=[x for x in hdrlines if not x.strip()=='']
    for line in hdrlines :
        sl=line.split(':')
        if len(sl)!=2 :
            raise Exception('Error parsing lfm header - expected single colon per line')
        key=sl[0]
        val=' '.join(sl[1].split())
        D[key]=val
    return D

    
    
    
