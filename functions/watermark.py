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

class Watermark():
    def __init__(self, path, path_logo, colors=(255, 255, 255), opacity=100):
        """
        Class to add a watermark to an image.

        Parameters
        ----------
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
        
        self.path = path
        self.file = self.path.split('/')[-1]
        self.path_logo = path_logo
        self.colors = colors
        self.opacity = (opacity / 100) * 255


    def img_color(self, image):
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
        
        logging.info('Changing the color of the logo to ' + str(self.colors) + '...')
        
        data = np.array(image)
        data[..., :-1] = self.colors
        image = Image.fromarray(data)
        
        logging.info('Changing the color done.')
        
        return image


    def img_resize(self, image):
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

        return image



    def img_opacity(self, image):
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
        
        logging.info(f'Changing opacity of the logo to {str(self.opacity)} out of 255...')
        
        alpha = image.split()[3]
        alpha = ImageEnhance.Brightness(alpha).enhance(self.opacity/255)
        image.putalpha(alpha)
        
        logging.info(f'Changed opacity of the logo to {str(self.opacity)} out of 255.')

        return image


    def logo_prep(self):
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

        logging.info(f'Transforming the logo in directory: {self.path_logo}')
        
        self.logo = Image.open(self.path_logo).convert("RGBA")
        self.logo = self.img_color(self.logo)
        self.logo = self.img_resize(self.logo)
        self.logo = self.img_opacity(self.logo)
        
        logging.info('Transformation of the logo done.')


    def img_watermark(self):
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
        
        logging.info(f'Adding the watermark on file: {self.file}')

        image = Image.open(self.path).convert("RGBA")
        self.logo_prep()
        
        width1, height1 = image.size
        width2, height2 = self.logo.size

        center_x, center_y = (width1//2), (height1//2)

        im2_x = int(center_x - (width2/2))
        im2_y = int(center_y - (height2/2))

        image.paste(self.logo, (im2_x, im2_y), self.logo)
            
        file = self.file.split('.')[0]
        path = self.path.rsplit('/', 1)[0]

        file_mrkd = f'{path}/{file}_mrkd.png'
        image.save(file_mrkd, 'PNG')
        
        logging.info(f'Watermark added successfully on file {self.file}.')
        logging.info(f'New file saved as {file}.')

        return file_mrkd


if __name__ == '__main__':
    colors = (255, 255, 255)
    opacity = 50
    folder_path = ''
    logo_path = ''
    
    wtmrk = Watermark(folder_path, logo_path, colors, opacity)
    wtmrk.img_watermark()
