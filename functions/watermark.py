# -*- coding: utf-8 -*-
"""
Created on Tue Nov 26 19:25:23 2024

@author: alram
"""

import logging
import os
import numpy as np
from PIL import Image, ImageEnhance
from pillow_heif import register_heif_opener


logger = logging.getLogger()

filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'log.log')
logging.basicConfig(filename='../log.log',
                    encoding='utf-8',
                    filemode='w',
                    level=logging.DEBUG,
                    format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p',
                    force=True)


def get_file(path):
    """
    Get the name of the files in a path.

    Parameters
    ----------
    path : String
        Path to folder where images are stored.

    Returns
    -------
    files : List
        Name of the files in the folder.

    """
    files = []
    for file in os.listdir(path):
        files.append(file)
        
    return files


def img_color(image, colors=(255, 255, 255)):
    """
    Change the color of the image. One color only.

    Parameters
    ----------
    image : PIL.Image
        Image of the logo.
    colors : Tuple, optional
        Color for the output. The default is (255, 255, 255).

    Returns
    -------
    image : PIL.Image
        Image with color changed.

    """
    
    logging.info('Chaging the color of the logo to ' + str(colors) + '...')
    
    data = np.array(image)
    data[..., :-1] = colors
    image = Image.fromarray(data)
    
    logging.info('Chaging the color done.')
    
    return image
    
    
def img_resize(image):
    """
    Change the size of the image.

    Parameters
    ----------
    image : PIL.Image
        Image to resize.

    Returns
    -------
    None.

    """
    
    logging.info('Changing the size of the logo...')
    
    resize = tuple(param/2 for param in image.size)
    image.thumbnail(resize, Image.LANCZOS)
    
    logging.info('Changing the size done.')


def img_opacity(image, opacity=120):
    """
    Change the opacity of an image.
    
    Parameters
    ----------
    image : PIL.Image
        Image to change the opacity.
    opacity : Integer, optional
        From 0 (transparent) to 255 (fully fisible). The default is 120.

    Returns
    -------
    None.

    """
    
    logging.info('Changing opacity of the logo to ' + str(opacity) + ' out of 255...')
    
    alpha = image.split()[3]
    alpha = ImageEnhance.Brightness(alpha).enhance(opacity/255)
    image.putalpha(alpha)
    
    logging.info('Changing opacity done.')


def logo_prep(path, colors=(255, 255, 255), opacity=120):
    """
    Preparing the logo to be added as a watermark.
    
    Parameters
    ----------
    path : String
        Path to folder where the logo is located.
    colors : Tuple, optional
        Color for the output. The default is (255, 255, 255).
    opacity : Integer, optional
        From 0 (transparent) to 255 (fully fisible). The default is 120.

    Returns
    -------
    logo : PIL.Image
        Logo prepared to be added as watermark.

    """

    logging.info('Preparing the logo...')
    
    logo = Image.open(path).convert("RGBA")
    logo = img_color(logo, colors)
    img_resize(logo)
    img_opacity(logo, opacity)
    
    logging.info('Preparing the logo done.')
    
    return logo


def img_watermark(file, folder_path, logo_path, colors=(255, 255, 255), opacity=120):
    """
    Add a watermark to an image.

    Parameters
    ----------
    file : String
        Name of the image where the watermark needs to be added.
    path : String
        Path to folder where the logo is located.
    colors : Tuple, optional
        Color for the output. The default is (255, 255, 255).
    opacity : Integer, optional
        From 0 (transparent) to 255 (fully visible). The default is 120.

    Returns
    -------
    None.

    """
    
    register_heif_opener()
    
    logging.info('Adding the watermark...')

    if (folder_path + "/" + file) == logo_path:
        return

    image = Image.open(folder_path + '\\' + file).convert("RGBA")
    logo = logo_prep(logo_path, colors=colors, opacity=opacity)
    
    width1, height1 = image.size
    width2, height2 = logo.size

    center_x, center_y = (width1//2), (height1//2)

    im2_x = int(center_x - (width2/2))
    im2_y = int(center_y - (height2/2))

    image.paste(logo, (im2_x, im2_y), logo)
    
    # Create a results folder if it does not already exists
    if not os.path.exists(folder_path + '\\results'):
        os.makedirs(folder_path + '\\results')
        
    file = file.split('.')[0]
    image.save(folder_path + '\\' + 'results' + '\\' + file + '.png', 'PNG')
    
    logging.info('Adding the watermark done.')
    logging.info(folder_path + '\\' + 'results' + '\\' + file + '.png')


def img_watermark_folder(folder_path, logo_path, colors=(255, 255, 255), opacity=20):
    """
    Add the watermark to all the images in the file path. Ignores anything
    that is not an image that PIL.Image cannot open.

    Parameters
    ----------
    colors : Tupe, optional
        Color for the output. The default is (255, 255, 255).
    opacity : Integer, optional
        From 0 (transparent) to 255 (fully fisible). The default is 120.

    Returns
    -------
    None.

    """

    logging.info('Folder path entered:' + folder_path)
    logging.info('Logo path entered:' + logo_path)
    
    files = get_file(folder_path)
    
    logging.info('Files available in the path:' + str(files))

    # Convert % into opacity number
    opacity = (opacity / 100) * 255

    for file in files:
        
        try:
            logging.info('Getting the file:' + file)

            img_watermark(file, folder_path, logo_path, colors=colors, opacity=opacity)
        except:
            logging.error('File ' + file + ' cannnot be open as an image.')
            pass


if __name__ == '__main__':
    colors = (255, 255, 255)
    opacity = 50
    folder_path = r'G:\Mon Drive\Travail\Ninamu Immobilier\Logo'
    logo_path = r'G:\Mon Drive\Travail\Ninamu Immobilier\Logo\logo.png'
    
    img_watermark_folder(folder_path, logo_path, colors=colors, opacity=opacity)