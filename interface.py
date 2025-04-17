from tkinter import *
from tkinter import filedialog
from tkinter import messagebox

from functions.watermark import img_watermark_folder
import logging
import os

logger = logging.getLogger()

filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'log.log')
logging.basicConfig(filename=filename,
                    encoding='utf-8',
                    filemode='w',
                    level=logging.DEBUG,
                    format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p',
                    force=True)

def ask_directory(folder_path):
    filename = filedialog.askdirectory()
    folder_path.set(filename)
    return filename

def ask_file(folder_path):
    filename = filedialog.askopenfilename()
    folder_path.set(filename)
    return filename

def validate(*args):
    if (folder_path_logo.get() != '') & (folder_path_pic.get() != '') & (opacity_default.get().isdigit()):
        transform_button.config(state='normal')
    else:
        transform_button.config(state='disabled')


root = Tk()
root.geometry("400x400")
root.title('Logo')

pady = (0,10)

folder_path_logo = StringVar()
folder_path_pic = StringVar()
opacity_default = StringVar(master=root, value='20')

def img_func():

    try:
        img_watermark_folder(folder_path=folder_path_pic.get(),
                             logo_path=folder_path_logo.get(),
                             opacity=int(opacity_default.get()))
    except Exception as e:
        messagebox.showerror(title = "Exception raised", message = str(e))

label = Label(master=root, text='Paramètres', font=('Helvetica', 12, 'bold'))
label_logo = Label(master=root, text='Sélectionner le fichier du logo', font=('Helvetica', 10))
path_logo = Label(master=root, textvariable=folder_path_logo, font=('Helvetica', 10))
button_logo = Button(text='Browse', command= lambda: ask_file(folder_path_logo))
label_pic = Label(master=root, text='Sélectionner le dossier contenant les photos à modifier', font=('Helvetica', 10))
path_pic = Label(master=root, textvariable=folder_path_pic, font=('Helvetica', 10))
button_pic = Button(text='Browse', command= lambda: ask_directory(folder_path_pic))
label_opacity = Label(master=root, text='Sélectionner le pourcentage d\'opacité sur logo', font=('Helvetica', 10))
opacity = Entry(master=root, textvariable=opacity_default, width=5)
perc_opacity = Label(master=root, text='%', font=('Helvetica', 10))
transform_button = Button(master=root, text='Transformer', command=img_func)

label.grid(row=0, column=0, columnspan=2, sticky='w', pady=pady)
label_logo.grid(row=1, column=0, columnspan=2, sticky='w')
path_logo.grid(row=2, column=1, sticky='w')
button_logo.grid(row=2, column=0, sticky='w', pady=pady)
label_pic.grid(row=4, column=0, columnspan=2, sticky='w')
path_pic.grid(row=5, column=1, sticky='w')
button_pic.grid(row=5, column=0, sticky='w', pady=pady)
label_opacity.grid(row=6, column=0, columnspan=2, sticky='w')
perc_opacity.grid(row=7, column=1, sticky='w')
opacity.grid(row=7, column=0, sticky='w', pady=pady)
transform_button.grid(row=8, column=0, columnspan=2, sticky='s')

transform_button.config(state='disabled')
folder_path_logo.trace('w', validate)
folder_path_pic.trace('w', validate)
opacity_default.trace('w', validate)

root.mainloop()