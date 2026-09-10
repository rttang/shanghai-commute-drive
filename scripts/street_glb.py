"""Lossless static glTF assembly; binary geometry and image bytes stay intact.

Only static street meshes are accepted. Cars, animations and skeletons cannot
silently enter the master. Shared prototype meshes remain shared instances.
"""
import copy
import hashlib
import json
import math
import os
import pathlib
import struct


def read_glb(path):
    data = pathlib.Path(path).read_bytes()
    magic, version, size = struct.unpack_from('<III', data)
    assert magic == 0x46546C67 and version == 2 and size == len(data), path
    cursor = 12
    document, binary = None, b''
    while cursor < len(data):
        length, kind = struct.unpack_from('<II', data, cursor)
        chunk = data[cursor + 8:cursor + 8 + length]
        if kind == 0x4E4F534A:
            document = json.loads(chunk)
        elif kind == 0x004E4942:
            binary = chunk
        cursor += 8 + length
    assert document is not None
    return document, binary


def write_glb(path, document, binary):
    document = copy.deepcopy(document)
    document['buffers'] = [{'byteLength': len(binary)}]
    js = json.dumps(document, ensure_ascii=False, separators=(',', ':')).encode()
    js += b' ' * (-len(js) % 4)
    total_bytes = 28 + len(js) + len(binary) + (-len(binary) % 4)
    if total_bytes > 0xffffffff:
        raise ValueError('A GLB cannot exceed its uint32 file-size limit; split the master into multiple GLBs. Runtime street assets may total up to 5 GB.')
    binary = bytes(binary) + b'\0' * (-len(binary) % 4)
    data = (struct.pack('<III', 0x46546C67, 2, 28 + len(js) + len(binary)) +
            struct.pack('<II', len(js), 0x4E4F534A) + js +
            struct.pack('<II', len(binary), 0x004E4942) + binary)
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.writing')
    expected = hashlib.sha256(data).hexdigest()
    def digest(file):
        result = hashlib.sha256()
        with file.open('rb') as reader:
            for block in iter(lambda: reader.read(4 * 1024 * 1024), b''):
                result.update(block)
        return result.hexdigest()
    # Large single-write copies on this external volume have produced a valid
    # file length with different bytes. Never publish an unchecked payload or
    # change the expected hash to agree with a damaged copy.
    for attempt in range(3):
        with temporary.open('wb') as writer:
            view = memoryview(data)
            for offset in range(0, len(data), 4 * 1024 * 1024):
                writer.write(view[offset:offset + 4 * 1024 * 1024])
            writer.flush()
            os.fsync(writer.fileno())
        if digest(temporary) == expected:
            temporary.replace(target)
            if digest(target) == expected:
                return {'bytes': len(data), 'sha256': expected}
        print(f'GLB write verification retry {attempt + 1}: {target}', flush=True)
    raise RuntimeError(f'GLB write failed byte verification: {target}')


class Assembly:
    arrays = ('bufferViews', 'accessors', 'images', 'samplers', 'textures',
              'materials', 'meshes', 'nodes', 'cameras')

    def __init__(self):
        self.doc = {'asset': {'version': '2.0', 'generator': 'Shanghai street master lossless assembly'},
                    'scene': 0, 'scenes': [{'name': 'Shanghai streets', 'nodes': []}]}
        self.doc.update({key: [] for key in self.arrays})
        self.binary = bytearray()
        self.cache = {}

    def resource(self, path):
        key = str(pathlib.Path(path).resolve())
        if key in self.cache:
            return self.cache[key]
        src, binary = read_glb(path)
        assert not src.get('animations') and not src.get('skins'), 'Street assets must be static'
        assert len(src.get('buffers', [])) <= 1 and not src.get('buffers', [{}])[0].get('uri')
        src = copy.deepcopy(src)
        triangle_count = self.triangles(src)
        offsets = {k: len(self.doc[k]) for k in self.arrays}
        self.binary += b'\0' * (-len(self.binary) % 4)
        binary_offset = len(self.binary)
        # Discard only the GLB format alignment; never mesh or image data.
        length = src.get('buffers', [{'byteLength': len(binary)}])[0]['byteLength']
        self.binary.extend(binary[:length])
        for v in src.get('bufferViews', []):
            v['buffer'] = 0
            v['byteOffset'] = v.get('byteOffset', 0) + binary_offset
        for a in src.get('accessors', []):
            if 'bufferView' in a:
                a['bufferView'] += offsets['bufferViews']
            if 'sparse' in a:
                for kind in ('indices', 'values'):
                    a['sparse'][kind]['bufferView'] += offsets['bufferViews']
        for image in src.get('images', []):
            assert 'uri' not in image, f'External image must be embedded: {path}'
            image['bufferView'] += offsets['bufferViews']
        for texture in src.get('textures', []):
            if 'source' in texture:
                texture['source'] += offsets['images']
            if 'sampler' in texture:
                texture['sampler'] += offsets['samplers']
            for ext in texture.get('extensions', {}).values():
                if isinstance(ext, dict) and 'source' in ext:
                    ext['source'] += offsets['images']

        def material_textures(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k.endswith('Texture') and isinstance(v, dict) and 'index' in v:
                        v['index'] += offsets['textures']
                    else:
                        material_textures(v)
            elif isinstance(obj, list):
                for item in obj:
                    material_textures(item)
        for material in src.get('materials', []):
            material_textures(material)
        for mesh in src.get('meshes', []):
            for primitive in mesh['primitives']:
                for k in primitive['attributes']:
                    primitive['attributes'][k] += offsets['accessors']
                if 'indices' in primitive:
                    primitive['indices'] += offsets['accessors']
                if 'material' in primitive:
                    primitive['material'] += offsets['materials']
                assert not primitive.get('targets'), 'Morphs are outside street assembly scope'
                draco = primitive.get('extensions', {}).get('KHR_draco_mesh_compression')
                if draco:
                    draco['bufferView'] += offsets['bufferViews']
        for node in src.get('nodes', []):
            if 'mesh' in node:
                node['mesh'] += offsets['meshes']
            if 'camera' in node:
                node['camera'] += offsets['cameras']
            if 'children' in node:
                node['children'] = [n + offsets['nodes'] for n in node['children']]
            for a, i in node.get('extensions', {}).get('EXT_mesh_gpu_instancing', {}).get('attributes', {}).items():
                node['extensions']['EXT_mesh_gpu_instancing']['attributes'][a] = i + offsets['accessors']
        roots = [n + offsets['nodes'] for n in src['scenes'][src.get('scene', 0)]['nodes']]
        for k in self.arrays:
            self.doc[k].extend(src.get(k, []))
        for k in ('extensionsUsed', 'extensionsRequired'):
            for ext in src.get(k, []):
                if ext not in self.doc.setdefault(k, []):
                    self.doc[k].append(ext)
        # Store a template subtree; repeated placement copies nodes, never buffers.
        count = len(src.get('nodes', []))
        result = {'roots': roots, 'start': offsets['nodes'], 'count': count,
                  'triangles': triangle_count, 'placed': False}
        self.cache[key] = result
        return result

    @staticmethod
    def triangles(doc):
        return sum(doc['accessors'][p['indices']]['count'] // 3 if 'indices' in p else
                   doc['accessors'][p['attributes']['POSITION']]['count'] // 3
                   for m in doc.get('meshes', []) for p in m['primitives'] if p.get('mode', 4) == 4)

    def place(self, path, name, center=(0, 0), heading=0, height=0, scale=(1, 1, 1), extras=None):
        resource = self.resource(path)
        roots = resource['roots']
        if resource['placed']:
            shift = len(self.doc['nodes']) - resource['start']
            nodes = copy.deepcopy(self.doc['nodes'][resource['start']:resource['start'] + resource['count']])
            for node in nodes:
                if 'children' in node:
                    node['children'] = [n + shift for n in node['children']]
            self.doc['nodes'].extend(nodes)
            roots = [r + shift for r in roots]
        resource['placed'] = True
        node = {'name': name, 'children': roots,
                'translation': [center[0], height, center[1]],
                'rotation': [0, math.sin(heading / 2), 0, math.cos(heading / 2)],
                'scale': list(scale)}
        if extras:
            node['extras'] = extras
        self.doc['scenes'][0]['nodes'].append(len(self.doc['nodes']))
        self.doc['nodes'].append(node)
        return resource['triangles']

    def write(self, path):
        return write_glb(path, {k: v for k, v in self.doc.items() if v != []}, self.binary)
