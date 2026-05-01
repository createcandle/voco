import sys
import json

#print("in increment_manifest_version.py")
try:
    with open('manifest.json', 'r+') as manifest_file:
        #manifest_file.seek(0)
        #print("manifest.json opened OK: ", type(manifest_file), manifest_file)
        manifest_file.seek(0)
        content = manifest_file.read()
        #print("content: ", type(content), "\n", content, "\n")
        content = content.strip().rstrip()
        if isinstance(content,str) and len(content) > 10 and 'version' in content:
            #print("content looks valid enough: ", content)
            data = json.loads(str(content))
            #print("data loaded")
            #print("MANIFEST BEFORE: \n\n", json.dumps(data, indent=4), "\n\n")
    
            if data and 'version' in data:
                version_parts = str(data['version']).split('.')
                #print("len(version_parts): ", len(version_parts), "\nversion_parts: ", version_parts)
            
                if len(version_parts) == 3:
                    version_parts[2] = str(int(version_parts[2]) + 1)
                    data['version'] = ".".join(version_parts)
                    #print("new version: ", data['version'])
                    
                    new_manifest = json.dumps(data, indent=4)
                    new_manifest = new_manifest.strip()
                    if isinstance(new_manifest,str) and 'version' in new_manifest:
                        #print("MANIFEST AFTER: \n\n", new_manifest, "\n\n")
                        manifest_file.seek(0)
                        manifest_file.truncate()
                        #file.truncate([size])
                        manifest_file.write(new_manifest)
                        print(str(data['version']), end="")
                        #manifest_file.close()
                        sys.exit(0)

except json.JSONDecodeError as ex:
    pass
    #print("increment_manifest_version: caught json decode error: ", ex)

except Exception as ex:
    pass
    #print("increment_manifest_version: caught error: ", ex)

#print("increment_manifest_version.py FAILED")
print("error", end="")
sys.exit(1)