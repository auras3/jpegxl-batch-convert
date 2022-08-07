import os
import subprocess
from tqdm import tqdm
import asyncio
from pprint import pprint


# Names must be ASCII
INPUT_FOLDER = r'path/to/input/folder'
OUTPUT_FOLDER = r'path/to/output/folder'
NUM_THREADS = 24


def get_valid_folder_name(folder_name):
    valid = ''
    for c in folder_name:
        if not c.isascii():
            valid += f'[u{ord(c)}]'
        else:
            valid += c

    return valid


def fix_folder_names(path):
    new_old_names = []
    for folder in os.listdir(path):
        full_path = os.path.join(path, folder)
        if os.path.isdir(full_path):
            new_path = full_path
            if not folder.isascii():
                new_path = os.path.join(path, get_valid_folder_name(folder))
                os.rename(full_path, new_path)
                new_old_names.append((new_path, full_path))

            new_old_names.extend(fix_folder_names(new_path))

    return new_old_names


def get_images(path):
    images = []
    for f in os.listdir(path):
        full_path = os.path.join(path, f)
        if os.path.isfile(full_path):
            if f.endswith('.jxl'):
                images.append(full_path)
        elif os.path.isdir(full_path):
            images.extend(get_images(full_path))

    return images


async def convert_to_jpg(jxl_file_path, jpg_file_path):
    proc = await asyncio.create_subprocess_exec(
        'djxl.exe',
        jxl_file_path, '--pixels_to_jpeg', '--jpeg_quality=90', '--quiet', jpg_file_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT
    )
    await proc.wait()
    return proc.returncode == 0


def get_output_folder_path(image_path):
    folder, _ = os.path.split(image_path)
    rel_image_path = os.path.relpath(folder, INPUT_FOLDER)
    return os.path.join(OUTPUT_FOLDER, rel_image_path)


async def convert_batch(batch, pbar):
    for im in batch:
        _, image_name = os.path.split(im)
        output_image_path = os.path.join(get_output_folder_path(im), image_name.split('.')[0] + '.jpg')
        await convert_to_jpg(im, output_image_path)
        pbar.update()


async def main():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)


    # jxlib doesn't support unicode names, so convert them into something valid
    # Save the old folder names so that we can change them back after conversion
    new_old_names = fix_folder_names(INPUT_FOLDER)
    print('(New name, old name):')
    pprint(new_old_names)

    # Create the folder structure in the output folder
    images = get_images(INPUT_FOLDER)
    for im in images:
        output_folder_path = get_output_folder_path(im)

        if not os.path.exists(output_folder_path):
            os.makedirs(output_folder_path, exist_ok=True)


    # Start batch conversion
    batches = [images[i::NUM_THREADS] for i in range(NUM_THREADS)]
    pbar = tqdm(total=len(images))
    tasks = [asyncio.create_task(convert_batch(batch, pbar)) for batch in batches]
    for t in tasks:
        await t


    # Change the folder names back to their original name
    for new_name, old_name in reversed(new_old_names):
        try:
            # Rename input folders
            os.rename(new_name, old_name)

            # We also need to rename the output folders
            # Since the directory structure is the same, we can just get the relative paths and
            # join them with the output folder path
            rel_new_name = os.path.relpath(new_name, INPUT_FOLDER)
            output_new_name = os.path.join(OUTPUT_FOLDER, rel_new_name)
            rel_old_name = os.path.relpath(old_name, INPUT_FOLDER)
            output_old_name = os.path.join(OUTPUT_FOLDER, rel_old_name)
            os.rename(output_new_name, output_old_name)
        except Exception as e:
            print(e)



if __name__ == '__main__':
    asyncio.run(main())
