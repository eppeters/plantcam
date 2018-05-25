import glob
import io
import os

import boto3
import click

import imageio
import progressbar
from PIL import Image, ImageStat

MINIMUM_S3_MULTIPART_PART_SIZE_IN_BYTES = 1024 * 1024 * 5
CROP_POINTS = (722, 1230, 1812, 2048)
DARK_BAND_SUM_MAX = 50

band_median_sums = []


def is_dark_image(image):
    band_median_sum = sum(ImageStat.Stat(image).median)
    band_median_sums.append(band_median_sum)
    return band_median_sum <= DARK_BAND_SUM_MAX


def get_s3_client():
    if os.environ.get('AWS_CONTAINER_CREDENTIALS_RELATIVE_URI'):
        return boto3.client('s3')

    client = boto3.client(
        's3',
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'])
    return client


def local_image_files(indir, sort):
    return sorted(glob.glob(f'{indir}/*.jpg'), key=sort)


def s3_image_files(indir, sort, client):
    return sorted([o['Key'] for o in client.list_objects(Bucket='plantcam')['Contents']], key=sort)


def open_from_s3(bucket, key, client):
    obj = client.get_object(Bucket=bucket, Key=key)
    return obj['Body']


def new_multipart_upload_id(bucket, key, client):
    click.echo('Creating multipart upload.')
    multipart_upload = client.create_multipart_upload(Bucket=bucket, Key=key)
    multipart_upload = client.create_multipart_upload(Bucket=bucket, Key=key)
    multipart_upload_id = multipart_upload['UploadId']
    click.echo(f'Multipart upload created. UploadId: {multipart_upload_id}')
    return multipart_upload_id


def upload_file_part(part, bucket, key, part_number, multipart_upload_id, client):
    click.echo(f'Uploading part {part_number} of {bucket}/{key}')
    part = client.upload_part(
        Body=part, Bucket=bucket, Key=key, PartNumber=part_number, UploadId=multipart_upload_id)
    click.echo(f'Finished uploading part {part_number} of {bucket}/{key}')
    return {'ETag': part['ETag'], 'PartNumber': part_number}


def finish_multipart_upload(bucket, key, parts, multipart_upload_id, client):
    click.echo(f'Finalizing multipart upload of {bucket}/{key}. UploadId: {multipart_upload_id}')
    client.complete_multipart_upload(
        Bucket=bucket, Key=key, UploadId=multipart_upload_id, MultipartUpload={'Parts': parts})
    click.echo(f'Finished multipart upload of {bucket}/{key}. UploadId: {multipart_upload_id}')


@click.command()
@click.option('--s3-in/--local-in', default=False)
@click.option('--s3-out/--local-out', default=False)
@click.option('--fps', default=30)
@click.option('--small/--not-small', default=False)
@click.option('--skip-dark-frames/--keep-dark-frames', default=True)
@click.option('--num-frames', default=None, type=int)
@click.option('--colors', default=256)
@click.option('--show-progress/--no-progress', default=True)
@click.argument('outfile')
@click.argument('indir')
def generate(s3_in, s3_out, fps, small, skip_dark_frames, num_frames, colors, outfile, indir,
             show_progress):
    s3_client = None
    if s3_in or s3_out:
        s3_client = get_s3_client()
    if s3_in:
        image_files = s3_image_files(indir, lambda f: int(f[:-4]), s3_client)
    else:
        s3_client = None
        image_files = local_image_files(indir, lambda f: int(f[len(indir) + 1:-4]))
    if num_frames:
        image_files = image_files[:num_frames]

    click.echo(f'{len(image_files)} files...')
    click.echo(f'FPS of gif: {fps}')

    if show_progress:
        image_files = progressbar.progressbar(image_files)

    multipart_upload_id = None
    outbucket = None
    outkey = None
    upload_parts = None
    if s3_out:
        upload_parts = []
        outbucket = outfile.split('/')[0]
        outkey = outfile.split('/')[-1]
        outfile = io.BytesIO()
        multipart_upload_id = new_multipart_upload_id(outbucket, outkey, s3_client)
    with imageio.get_writer(
            outfile, mode='I', format='gif-pil', fps=fps, subrectangles=small,
            palettesize=colors) as writer:
        part_number = 1
        for filename in image_files:
            if not show_progress:
                click.echo(f'Processing {filename}')
            if s3_in:
                file_obj = open_from_s3(indir, filename, s3_client)
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
            if s3_out and outfile.tell() > MINIMUM_S3_MULTIPART_PART_SIZE_IN_BYTES:
                outfile.seek(0)
                part = upload_file_part(outfile, outbucket, outkey, part_number,
                                        multipart_upload_id, s3_client)
                upload_parts.append(part)
                outfile.truncate()
                outfile.seek(0)
                part_number = part_number + 1
            if not show_progress:
                click.echo(f'Processing {filename}')
    if s3_out:
        click.echo('Uploading the last part, which may be smaller than 5MB')
        outfile.seek(0)
        part = upload_file_part(outfile, outbucket, outkey, part_number, multipart_upload_id,
                                s3_client)
        upload_parts.append(part)
        outfile.truncate()
        finish_multipart_upload(outbucket, outkey, upload_parts, multipart_upload_id, s3_client)
        s3_client.put_object_acl(Bucket=outbucket, Key=outkey, ACL='public-read')

if __name__ == '__main__':
    generate()
