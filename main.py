import pytube
import requests
from tkinter import *
from tkinter import filedialog
from PIL import Image, ImageTk 

root = Tk()
root.title("YouSave")
root.iconbitmap("télécharger.ico")
root.geometry("780x1080")
root.config(background="sky blue")

# Fonction pour télécharger une vidéo
def download_video():
    url = video_url.get()
    yt = pytube.YouTube(url)
    video_streams = yt.streams.filter(progressive=True)
    video_quality = quality.get()
    if video_quality == "720HD":
        stream = video_streams.get_by_resolution("720HD")
    elif video_quality == "480":
        stream = video_streams.get_by_resolution("480p")
    elif video_quality == "360":
        stream = video_streams.get_by_resolution("360p")
    elif video_quality == "144":
        stream = video_streams.get_by_resolution("144p")
    else:
        stream = video_streams.first()
    save_path = filedialog.askdirectory()
    stream.download(save_path)

# Fonction pour télécharger une image
def download_image():
    url = image_url.get()
    response = requests.get(url)
    save_path = filedialog.askdirectory()
    with open(save_path + "/image.jpg", "wb") as f:
        f.write(response.content)

# Charger l'image de fond
background_image = Image.open("photo_2024-04-07_19-52-14.jpg")
background_photo = ImageTk.PhotoImage(background_image)
background_label = Label(root, image=background_photo)
background_label.place(x=0, y=0, relwidth=1, relheight=1)

# Création du menu
menu_bar = Menu(root)
root.config(menu=menu_bar)

# Ajout d'un menu "Fichier"
file_menu = Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="Fichier", menu=file_menu)
file_menu.add_command(label="Quitter", command=root.quit)

# Ajout d'un menu "Outils"
tools_menu = Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="Outils", menu=tools_menu)
tools_menu.add_command(label="Télécharger une vidéo", command=download_video)
tools_menu.add_command(label="Télécharger une image", command=download_image)

# Widgets pour télécharger une vidéo
video_label = Label(root, text="URL de la vidéo:")
video_label.grid(row=0, column=0, padx=10, pady=10, sticky=W)
video_url = Entry(root, width=90)
video_url.grid(row=0, column=1, padx=10, pady=10, columnspan=2)

quality_label = Label(root, text="Qualité de la vidéo:")
quality_label.grid(row=1, column=0, padx=10, pady=10, sticky=W)
quality = StringVar()
quality.set("720HD")
quality_dropdown = OptionMenu(root, quality, "720HD", "480", "360", "144")
quality_dropdown.grid(row=1, column=1, padx=10, pady=10)
video_button = Button(root, text="Télécharger la vidéo", command=download_video, bg="#33FFBF")
video_button.grid(row=1, column=2, padx=10, pady=10)

# Widgets pour télécharger une image
image_label = Label(root, text="URL de l'image:")
image_label.grid(row=2, column=0, padx=10, pady=10, sticky=W)
image_url = Entry(root, width=90)
image_url.grid(row=2, column=1, padx=10, pady=10, columnspan=2)

image_button = Button(root, text="Télécharger l'image", command=download_image, bg="#33FFBF")
image_button.grid(row=3, column=1, padx=10, pady=10)

root.mainloop()
