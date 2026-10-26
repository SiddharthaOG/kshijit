import boto3
from botocore.config import Config
from botocore import UNSIGNED

# Configure for anonymous (unsigned) access
s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED), region_name='us-east-1')

# Try to list tiles in the copernicus-dem-30m bucket for the Vijayawada area
# Vijayawada is approximately 16.5N, 80.6E
# Copernicus DEM GLO-30 tiles are 1x1 degree, named like Copernicus_DSM_COG_10_N{lat:02d}_E{lon:03d}.tif
# For Vijayawada (~16.5N, 80.6E), the tile would be N16E080

bucket = 'copernicus-dem-30m'

# Check the main tile for Vijayawada (N16E080)
prefix = 'Copernicus_DSM_COG_10_N16_00_E080_00_DEM/'
try:
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=10)
    print('N16E080 tile:')
    for obj in response.get('Contents', []):
        print('  {} ({} bytes)'.format(obj['Key'], obj['Size']))
except Exception as e:
    print('Error accessing N16E080: {}'.format(e))

# Also check nearby tiles
for lat in [15, 16, 17]:
    for lon in [79, 80, 81]:
        prefix = 'Copernicus_DSM_COG_10_N{:02d}_00_E{:03d}_00_DEM/'.format(lat, lon)
        try:
            response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=5)
            if 'Contents' in response:
                print('N{:02d}E{:03d} tile:'.format(lat, lon))
                for obj in response['Contents']:
                    print('  {} ({} bytes)'.format(obj['Key'], obj['Size']))
        except Exception as e:
            print('Error accessing N{:02d}E{:03d}: {}'.format(lat, lon, e))