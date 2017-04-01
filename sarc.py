import os, zlib
from struct import pack, unpack, calcsize

DEFAULT_HASH_KEY = 0x65

class Sarc:
    class BlockHeader(object):
        def check_valid(self):
            if self.signature != self.cSignature:
                raise ValueError('Invalid signature ( except: "%s", actual: "%s" )'%(self.cSignature, self.signature))
            if self.header_size != self.cStructSize:
                raise ValueError('Invalid header size ( except: %x, actual: %x )'\
                                 %(self.cStructSize, self.header_size))
    
    class ArchiveBlockHeader(BlockHeader):
        HEADER_STRUCT = '4sHHIIHH'
        cStructSize = calcsize(HEADER_STRUCT)
        cSignature = 'SARC'
        __cArchiveVersion = 0x0100
        
        def __init__(self, data = None, order = ''):
            if data:
                bom = data[6:8]
                self.order = '<' if (bom == '\xff\xfe') else '>'
                self.signature, self.header_size, self.bom, self.file_size,\
                                  self.data_block_offset, self.version, reserved = \
                                  unpack(self.order + self.HEADER_STRUCT, data[:self.cStructSize])
                self.__check_valid()
            else:
                self.order = order
                self.signature = self.cSignature
                self.header_size = self.cStructSize
                self.bom = 0xfeff
                self.file_size = 0
                self.data_block_offset = 0
                self.version = self.__cArchiveVersion
        
        def check_valid(self):
            super(Sarc.ArchiveBlockHeader, self).check_valid()
            if self.bom != 0xfeff:
                raise ValueError('Invalid BOM value ( except: %x, actual: %x )'%(0xfeff, self.bom))
            if self.version != self.__cArchiveVersion:
                raise ValueError('Invalid archive version ( except: %x, actual: %x )'\
                                 %(self.__cArchiveVersion, self.version))
        __check_valid = check_valid
        
        def pack(self):
            return pack(self.order + self.HEADER_STRUCT, self.cSignature, self.header_size, self.bom, self.file_size,\
                                  self.data_block_offset, self.version, 0)

    class FATBlockHeader(BlockHeader):
        HEADER_STRUCT = '4sHHI'
        cStructSize = calcsize(HEADER_STRUCT)
        cSignature = 'SFAT'
        __cArchiveEntryMax = 0x3fff
        
        def __init__(self, data = None, order = '', hash_key = DEFAULT_HASH_KEY):
            self.order = order
            if data:
                self.signature, self.header_size, self.file_count, self.hash_key = \
                            unpack(order + self.HEADER_STRUCT, data[:self.cStructSize])
                self.__check_valid()
            else:
                self.signature = self.cSignature
                self.header_size = self.cStructSize
                self.file_count = 0
                self.hash_key = hash_key
        
        def check_valid(self):
            super(Sarc.FATBlockHeader, self).check_valid()
            if self.file_count > self.__cArchiveEntryMax:
                raise ValueError('Invalid file count: %x'%self.file_count)
        __check_valid = check_valid
        
        def pack(self):
            return pack(self.order + self.HEADER_STRUCT, self.cSignature, \
                        self.header_size, self.file_count, self.hash_key)

    class FATEntry:
        ENTYR_STRUCT = 'IIII'
        cStructSize = calcsize(ENTYR_STRUCT)
        __cFNTAlign = 4
        
        ARCHIVED = 0
        FILESYSTEM = 1
        
        def __init__(self, data = None, order = '', base_path = '', file_path = '', hash_key = DEFAULT_HASH_KEY):
            self.order = order
            if data:
                self.type = self.ARCHIVED
                self.hash, self.name_offset, self.data_start_offset, self.data_end_offset = \
                            unpack(order + self.ENTYR_STRUCT, data[:self.cStructSize])
                self.__check_valid()
            else:
                self.type = self.FILESYSTEM
                self.path = file_path
                self.r_path = getrpath(base_path, file_path)
                self.hash = calchash(self.r_path, hash_key)
                self.name_offset = 0
                self.data_start_offset = 0
                self.data_end_offset = 0
        
        def __align_data(self, data, cur_pos):
            if self.__is_bflim(data):
                alignment = self.__read_bflim_alignment(data)
                return align(cur_pos, alignment) - cur_pos
            else:
                return 0
        
        def __align_fn(self, fn, alignment):
            return align(len(fn), alignment) - len(fn)
        
        def __is_bflim(self, data):
            return (data[-0x28:-0x24] == 'FLIM') and (len(data) == unpack(self.order + 'I', data[-0x1C:-0x18])[0])
        
        def __read_bflim_alignment(self, data):
            return unpack(self.order + 'H', data[-8:-6])[0]
        
        def archive(self, fnt_list, data_list, cur_fnt_offset, cur_data_offset):
            if self.type == self.ARCHIVED:
                return True
            elif self.type == self.FILESYSTEM:
                file_data = open(self.path, 'rb').read()
                feed = self.__align_data(file_data, cur_data_offset)
                if feed > 0:
                    data_list.append(feed * '\x00')
                    cur_data_offset += feed
                data_list.append(file_data)
                
                self.data_start_offset = cur_data_offset
                self.data_end_offset = cur_data_offset + len(file_data)
                self.name_offset = ((cur_fnt_offset / self.__cFNTAlign) & 0x00ffffff) | (1 << 24) # Always (1 << 24) ?
                
                r_path = self.r_path + '\x00'
                r_path += self.__align_fn(r_path, self.__cFNTAlign) * '\x00'
                cur_fnt_offset += len(r_path)
                fnt_list.append(r_path)
                
                return cur_fnt_offset, self.data_end_offset
        
        def check_valid(self):
            pass
        __check_valid = check_valid
        
        def extract(self, fnt_data, archive_data, path, save_file):
            if self.type == self.ARCHIVED:
                name_offset = self.name_offset & 0x00ffffff
                r_path = get_string(fnt_data[name_offset * self.__cFNTAlign:])
                
                outpath = os.path.join(path, r_path)
                outdir, name = os.path.split(outpath)
                
                if save_file:
                    mkdirs(outdir)
                    data = archive_data[self.data_start_offset:self.data_end_offset]
                    write_file(outpath, data)
                return r_path, outpath
            else:
                return '', ''
        
        def pack(self):
            return pack(self.order + self.ENTYR_STRUCT, \
                        self.hash, self.name_offset, self.data_start_offset, self.data_end_offset)
    
    class FNTBlockHeader(BlockHeader):
        HEADER_STRUCT = '4sHH'
        cStructSize = calcsize(HEADER_STRUCT)
        cSignature = 'SFNT'
        
        def __init__(self, data = None, order = ''):
            self.order = order
            if data:
                self.signature, self.header_size, reserved = \
                            unpack(order + self.HEADER_STRUCT, data[:self.cStructSize])
                self.__check_valid()
            else:
                self.signature = self.cSignature
                self.header_size = self.cStructSize
        
        def check_valid(self):
            super(Sarc.FNTBlockHeader, self).check_valid()
        __check_valid = check_valid
        
        def pack(self):
            return pack(self.order + self.HEADER_STRUCT, self.signature, self.header_size, 0)
    
    def __init__(self, path = '', order = '', hash_key = DEFAULT_HASH_KEY):
        if os.path.isfile(path):
            self.header, self.fatheader, self.entries, self.fnt_data, self.archive_data = self.__read_archive(path)
        elif os.path.isdir(path):
            self.__create_archive(path, order, hash_key)
    
    def __create_archive(self, path, order, hash_key):
        self.header = Sarc.ArchiveBlockHeader(order = order)
        self.fatheader = Sarc.FATBlockHeader(order = order, hash_key = hash_key)
        self.entries = None
        file_list = walk(path)
        for f in file_list:
            self.__add_file_entry(path, f)
        self.fnt_data = ''
        self.archive_data = ''
    
    def __read_archive(self, path):
        cur_pos = 0
        data = open(path,'rb').read()
        header = Sarc.ArchiveBlockHeader(data[cur_pos:cur_pos + Sarc.ArchiveBlockHeader.cStructSize])
        cur_pos += header.header_size
        fatheader = Sarc.FATBlockHeader(data = data[cur_pos:cur_pos + Sarc.FATBlockHeader.cStructSize], order = header.order)
        cur_pos += fatheader.header_size
        fatentries = []
        for i in range(fatheader.file_count):
            fatentries.append(Sarc.FATEntry(data = data[cur_pos:cur_pos + Sarc.FATEntry.cStructSize], order = header.order))
            cur_pos += Sarc.FATEntry.cStructSize
        entries = {e.hash:e for e in fatentries}
        fntheader = Sarc.FNTBlockHeader(data = data[cur_pos:cur_pos+Sarc.FNTBlockHeader.cStructSize], order = header.order)
        cur_pos += fntheader.header_size
        fnt_data = data[cur_pos:header.data_block_offset]
        archive_data = data[header.data_block_offset:]
        return header, fatheader, entries, fnt_data, archive_data
    
    def add_file_entry(self, base_path, file_path):
        entry = Sarc.FATEntry(order = self.header.order, base_path = base_path, file_path = file_path, hash_key = self.fatheader.hash_key)
        if self.entries:
            self.entries[entry.hash] = entry
        else:
            self.entries = {entry.hash:entry}
    __add_file_entry = add_file_entry
    
    def archive(self, archive_path, verbose = False):
        fnt_list = []
        data_list = []
        packed_fat_entries = []
        cur_fnt_offset = len(self.fnt_data)
        cur_data_offset = len(self.archive_data)
        sorted_entries = [self.entries[k] for k in sorted(self.entries.keys())]
        
        for e in sorted_entries:
            cur_fnt_offset, cur_data_offset = e.archive(fnt_list, data_list, cur_fnt_offset, cur_data_offset)
            packed_fat_entries.append(e.pack())
            if verbose:
                print 'Archived:', e.r_path
        self.fatheader.file_count = len(packed_fat_entries)
        
        archived_data = ''.join([self.header.pack(), self.fatheader.pack()])
        archived_data += ''.join(packed_fat_entries)
        archived_data += Sarc.FNTBlockHeader(order = self.header.order).pack()
        archived_data += self.fnt_data + ''.join(fnt_list)
        self.header.data_block_offset = len(archived_data)
        
        archived_data += self.archive_data + ''.join(data_list)
        self.header.file_size = len(archived_data)
        
        archive_file = open(archive_path, 'wb')
        archive_file.write(archived_data)
        archive_file.seek(0, 0)
        archive_file.write(self.header.pack())
        archive_file.close()
    
    def extract(self, path, all = False, name = None, hash = 0, save_file = True, verbose = False):
        if all:
            for k in self.entries:
                self.extract(path, all = False, name = None, hash = k, save_file = save_file, verbose = verbose)
        else:
            if name:
                hash = calchash(name, self.header.hash_key)
            if hash:
                r_path, full_path = self.entries[hash].extract(self.fnt_data, self.archive_data, path, save_file)
                if (save_file and full_path and verbose):
                    print 'Saved:', full_path
                elif (not save_file) and r_path:
                    print r_path

def align(value, alignment):
    return (value + alignment -1) / alignment *alignment

def calchash(data, key):
    ret = 0
    for c in data:
        ret = (ret * key + ord(c)) & 0xffffffff
    return ret

def get_string(data):
    ret = ''
    for c in data:
        if '\x00' == c:
            break
        ret += c
    return ret

def getrpath(base, full):
    ret = full[len(base):]
    while ret[0] in ['/','\\']:
        ret = ret[1:]
    return ret.replace('\\','/')

def mkdirs(path):
    if not os.path.exists(path):
        os.makedirs(path)

def walk(dirname):
    filelist = []
    for root,dirs,files in os.walk(dirname):
        for filename in files:
            fullname=os.path.join(root,filename)
            filelist.append(fullname)
    return filelist

def write_file(path, data):
    fs = open(path, 'wb')
    fs.write(data)
    fs.close()

#Helper methods
def create_archive(path, archive, order, hash_key, verbose):
    sarc = Sarc(path = path, order = order, hash_key = hash_key)
    sarc.archive(archive_path = archive, verbose = verbose)

def extract_archive(path, archive, verbose):
    sarc = Sarc(path = archive)
    sarc.extract(path = path, all = True, verbose = verbose)

def list_archive(archive):
    sarc = Sarc(path = archive)
    sarc.extract(path = '', all = True, save_file = False)

if '__main__' == __name__:
    extract_archive('./Horse_', './Horse_.sarc', True)
