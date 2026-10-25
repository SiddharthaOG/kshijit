import rasterio

for tile in ['N16E079', 'N16E080', 'N16E081']:
    path = f'data/raw/dem/{tile}.tif'
    with rasterio.open(path) as src:
        print(f'{tile}:')
        print(f'  NoData from tags: {src.tags()}')
        print(f'  NoData from profile: {src.profile.get("nodata")}')
        data = src.read(1)
        print(f'  Min value: {data.min()}')
        print(f'  Max value: {data.max()}')
        print()