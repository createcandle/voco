import sys
import json

print("in increment_manifest_version.py")
try:
    with open('manifest.json', 'w') as manifest_file:
        data = json.load(manifest_file)

        print("MANIFEST BEFORE: \n\n", json.dumps(data, indent=4), "\n\n")
    
        if 'version' in data:
            version_parts = str(version).split('.')
            print("len(version_parts): ", len(version_parts), "\nversion_parts: ", version_parts)
            
            if len(version_parts) == 3:
                version_parts[2] = int(version_parts[2]) + 1
                data['version'] = ".".join(version_parts)
                new_manifest = json.dumps(data, indent=4)
                
                print("MANIFEST AFTER: \n\n", new_manifest, "\n\n")
                manifest_file.truncate(0)
                manifest_file.write(new_manifest)
                #manifest_file.close()
                sys.exit(0)
                
except Exception as ex:
    print("increment_manifest_version: caught error: ", ex)

print("increment_manifest_version.py FAILED")
sys.exit(1)