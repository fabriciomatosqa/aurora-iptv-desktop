"""Synthetic local benchmark; no provider access or private data."""
import argparse
import cProfile
import json
from pathlib import Path
import tempfile
from time import perf_counter
from time import process_time
import os
from unittest.mock import patch
from aurora_desktop.catalog import LibraryV2

parser = argparse.ArgumentParser()
parser.add_argument('--size', type=int, default=10000)
parser.add_argument('--output', required=True)
parser.add_argument('--profile', action='store_true', help='Adds substantial overhead; use only for diagnosis')
args = parser.parse_args()
result = {'size': args.size, 'profiled_delta': args.profile, 'seconds': {}}
result['cpu_seconds'] = {}
def peak_memory_bytes():
    if os.name != 'nt':
        return None
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [(name, ctypes.c_size_t) for name in (
            'peak_working_set', 'working_set', 'peak_paged_pool', 'paged_pool',
            'peak_nonpaged_pool', 'nonpaged_pool', 'pagefile', 'peak_pagefile')]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    ok = ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(-1), ctypes.byref(counters), counters.cb)
    return counters.peak_working_set if ok else None
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
    root = Path(directory)
    source = root / 'synthetic.m3u'
    def write(extra=0):
        with source.open('w', encoding='utf-8') as stream:
            stream.write('#EXTM3U\n')
            for i in range(args.size + extra):
                kind = ('live', 'movie', 'series')[i % 3]
                title = f'Item {i}' if kind != 'series' else f'Show {i // 30} S01E{i % 30 + 1:02d}'
                stream.write(f'#EXTINF:-1 xui-id="{i}" group-title="{kind}",{title}\nhttps://example.invalid/{kind}/user/pass/{i}.ts\n')
    def measure(name, action):
        start = perf_counter()
        cpu_start = process_time()
        value = action()
        result['seconds'][name] = perf_counter() - start
        result['cpu_seconds'][name] = process_time() - cpu_start
        result['process_peak_working_set_bytes'] = peak_memory_bytes()
        Path(args.output).write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(name, result['seconds'][name], flush=True)
        return value
    write()
    lib = LibraryV2(root / 'catalog.db')
    connect = lib.connect
    def traced_connect():
        db = connect()
        previous = [perf_counter(), '']
        def trace(sql):
            if sql.startswith('CREATE TEMP TABLE key_remaps AS'):
                print('REMAP PLAN', [tuple(r) for r in db.execute('EXPLAIN QUERY PLAN ' + sql.split(' AS', 1)[1])], flush=True)
            now = perf_counter()
            if now - previous[0] > .5 and previous[1]:
                print('SQL', round(now - previous[0], 3), previous[1][:500], flush=True)
            previous[:] = [now, sql]
        db.set_trace_callback(trace)
        return db
    lib.connect = traced_connect
    pid = lib.add_playlist('Synthetic', str(source))
    with patch('aurora_desktop.catalog.get_provider_category_kinds', return_value={}), patch('aurora_desktop.catalog.get_provider_series_posters', return_value={}):
        measure('first_import', lambda: lib.import_playlist(pid))
        measure('reopen_local', lambda: LibraryV2(root / 'catalog.db').items(pid, 'live', limit=48))
        measure('unchanged', lambda: lib.import_playlist(pid))
        write(2)
        profiler = cProfile.Profile()
        if args.profile:
            profiler.enable()
        measure('two_added', lambda: lib.import_playlist(pid))
        if args.profile:
            profiler.disable()
            profiler.dump_stats(args.output + '.profile')
        for kind in ('live', 'movie', 'series'):
            measure('page_' + kind, lambda: lib.items(pid, kind, limit=48))
    with lib.connect() as db:
        result['batch_plan'] = [tuple(r) for r in db.execute('EXPLAIN QUERY PLAN SELECT rowid,key,title FROM items WHERE playlist_id=? AND rowid>? ORDER BY rowid LIMIT 1200', (pid, 0))]
Path(args.output).write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result), flush=True)
