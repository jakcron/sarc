# Nintendo Ware Layout SHArchive Tool
## Usage:
### Using as a script:
```
sarc.py [-h] [-v] (-x | -c | -l) [-e {big,little}] [-k HASHKEY]
        [-d DIR] -f ARCHIVE
```

```
optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         Enable verbose output
  -x, --extract         Extract the archive
  -c, --create          Create an archive
  -l, --list            List contents of the archive
  -e {big,little}, --endianess {big,little}
                        Set archive endianess
  -k HASHKEY, --hashkey HASHKEY
                        Set hash key
  -d DIR, --dir DIR     Set working directory
  -f ARCHIVE, --archive ARCHIVE
                        Set archive file
```
### Import as a module:
```Python
from sarc import *

#Initialize an archive with a file:
arc = Sarc('Path/To/Archive')

#Initialize an archive with a directory:
arc = Sarc(path='Path/To/Directory/', order='<', hash_key=0x65)

#Add a file to the archive:
arc.add_file_entry('Path/to/File')

#Save the archive:
arc.archive(archive_path='Path/To/Archive')

#Extract the archive file entries:
arc.extract(path='Path/To/Output/', all=True)

#Extract a single file from the archive by name:
arc.extract(path='Path/To/Output/', name='Name/Of/File')

#Extract a single file from the archive by hash:
arc.extract(path='Path/To/Output/', hash=0x12345678)

#List out all file entries (Hash and Name):
arc.extract(path='', all=True, save_file=False)
```
