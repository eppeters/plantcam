import glob
import io
import os

import boto3
import click

import imageio
import progressbar
from PIL import Image, ImageStat

CROP_POINTS = (722, 1230, 1812, 2048)
DARK_BAND_SUM_MAX = 50

band_median_sums = []


def is_dark_image(image):
    band_median_sum = sum(ImageStat.Stat(image).median)
    band_median_sums.append(band_median_sum)
    return band_median_sum <= DARK_BAND_SUM_MAX


def s3_client():
    if os.environ.get('AWS_CONTAINER_CREDENTIALS_RELATIVE_URI'):
        return boto3.client('s3')

    client = boto3.client(
        's3',
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'])
    return client


timestamp_sort = lambda f: int(f[len(indir) + 1:-4])


def local_image_files(indir, sort):
    return sorted(glob.glob(f'{indir}/*.jpg'), key=sort)


def s3_image_files(indir, sort, client):
    return sorted([o['Key'] for o in client.list_objects(Bucket='plantcam')['Contents']], key=sort)


@click.command()
@click.option('--s3/--local', default=False)
@click.option('--fps', default=30)
@click.option('--small/--not-small', default=False)
@click.option('--skip-dark-frames/--keep-dark-frames', default=True)
@click.option('--num-frames', default=None, type=int)
@click.option('--colors', default=256)
@click.option('--show-progress/--no-progress', default=True)
@click.argument('outfile')
@click.argument('indir')
def generate(s3, fps, small, skip_dark_frames, num_frames, colors, outfile, indir, show_progress):
    s3_client = None
    if s3:
        s3_client = s3_client()
        image_files = s3_image_files(indir, timestamp_sort, s3_client)
    else:
        image_files = local_image_files(indir, timestamp_sort)

    if num_frames:
        image_files = image_files[:num_frames]
    click.echo(f'{len(image_files)} files...')
    click.echo(f'FPS of gif: {fps}')
    with imageio.get_writer(
            outfile, mode='I', format='gif-pil', fps=fps, subrectangles=small,
            palettesize=colors) as writer:
        if show_progress:
            image_files = progressbar.progressbar(image_files)
        for filename in image_files:
            if s3:
                file_obj = open_from_s3(indir, filename)
            else:
                file_obj = open(filename, 'rb')
            with Image.open(file_obj) as fullsize_image:
                cropped_image = fullsize_image.crop(CROP_POINTS)
                if skip_dark_frames and is_dark_image(cropped_image):
                    continue
                jpeg_bytes = io.BytesIO()
                cropped_image.save(jpeg_bytes, format='jpeg')
            jpeg_bytes.seek(0)
            image = imageio.imread(jpeg_bytes, format='jpeg-pil')
            writer.append_data(image)

if __name__ == '__main__':
    generate()
