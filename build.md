
## Build a documentation
mkdocs build --clean --site-dir /home/xavier/Projects/SMBYC/smbyc.bitbucket.org/qgisplugins/cloudmasking/

## Deploy
pb_tool deploy

## Zip
pb_tool zip

## upload
python2 plugin_upload.py -u xaviercll CloudMasking.zip
