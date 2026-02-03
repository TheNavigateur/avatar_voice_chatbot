import struct
import json
import os

def parse_glb(file_path):
    with open(file_path, 'rb') as f:
        # Header
        magic = f.read(4)
        if magic != b'glTF':
            print("Error: Not a GLB file")
            return
        
        version, length = struct.unpack('<II', f.read(8))
        print(f"GLB Version: {version}")
        print(f"Total Length: {length} bytes")
        
        # Chunk 0: JSON
        chunk_length, chunk_type = struct.unpack('<II', f.read(8))
        if chunk_type != 0x4E4F534A: # JSON
            print("Error: First chunk is not JSON")
            return
        
        json_data = f.read(chunk_length)
        data = json.loads(json_data)
        
        print("\n--- JSON Content Summary ---")
        if 'asset' in data:
            print(f"Asset Info: {data['asset']}")
            
        if 'meshes' in data:
            print(f"Meshes Found: {len(data['meshes'])}")
            for i, mesh in enumerate(data['meshes']):
                print(f"  Mesh {i}: {mesh.get('name', 'Unnamed')}")
                for primitive in mesh.get('primitives', []):
                    attr = primitive.get('attributes', {})
                    print(f"    Primitive: Attributes: {list(attr.keys())}")
                    if 'targets' in primitive:
                        print(f"    Morph Targets Present: Yes ({len(primitive['targets'])} targets)")
                
                # Check for morph target names in extras
                if 'extras' in mesh and 'targetNames' in mesh['extras']:
                    print(f"    Morph Target Names: {mesh['extras']['targetNames']}")
                elif 'weights' in mesh:
                    print(f"    Morph Weights Present: {mesh['weights']} (Names likely missing in JSON)")
        else:
            print("WARNING: No meshes found in file!")
            
        if 'nodes' in data:
            print(f"Nodes Found: {len(data['nodes'])}")
            # Check for scale/translation on root nodes
        
        if 'skins' in data:
            print(f"Skins Found: {len(data['skins'])}") # Facial animation needs skins/morphs
            
        if 'images' in data:
             print(f"Images (Textures) Found: {len(data['images'])}")
        else:
             print("WARNING: No images/textures found (might be untextured)")


if __name__ == "__main__":
    if os.path.exists('static/avatar.glb'):
        print("\n=== INSPECTING avatar.glb ===")
        parse_glb('static/avatar.glb')
    
    if os.path.exists('static/jackie.glb'):
        print("\n=== INSPECTING jackie.glb ===")
        parse_glb('static/jackie.glb')
