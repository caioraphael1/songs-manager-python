#!/usr/bin/env python3
"""
Instalação:
    pip install customtkinter

Uso:
    python songs_manager.py [caminho_do_banco.db]

Build:
    pip install pyinstaller
    pyinstaller --onefile --windowed songs_manager.py
pyinstaller --onefile --windowed --collect-all customtkinter songs_manager.py


pyinstaller --onefile --windowed --collect-all customtkinter --distpath . --workpath ./build_temp --specpath ./build_temp songs_manager.py
"""
import sqlite3
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
import webbrowser
from urllib.parse import urlparse, parse_qs

import customtkinter as ctk

SCHEMA = """
CREATE TABLE IF NOT EXISTS musicas (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    link TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS musicas_tags (
    musica_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (musica_id, tag_id),
    FOREIGN KEY (musica_id) REFERENCES musicas(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
"""

PLAY_COLUMN = "#1"   # 3rd displayed column (Treeview columns are 1-based: #1, #2, #3)

AZUL     = ("#3d7fe0", "#3d7fe0")     # h2
AMARELO  = ("#b89b00", "#eecf1d")     # h3
LARANJA  = ("#e06e00", "#ff8513")     # h4
VERMELHO = ("#f04545", "#f04545")     # h5
ROSA     = ("#e0568f", "#ff82b2")     # h6

ACCENT       = AZUL
ACCENT_HOVER = ("#2f68bd", "#2f68bd")
DANGER       = VERMELHO
PERIGO_HOVER = ("#d13030", "#d13030")

BG_JANELA = ("#f2f3f5", "#1a1a1a")
BG_CARD   = ("#ffffff", "#262626")
BORDA     = ("#dcdfe4", "#3a3a3a")       # --study-overflow-border
COR_TEXTO = ("#2e3338", "#dcddde")   # --note-text
COR_MUTED = ("#6b7280", "#8b8d91")

RADIUS_CARD = 8   # cantos do #note-tab_content
RADIUS      = 4   # cantos de tabelas, imagens, código

BG     = "#262626"
FG     = "#dcddde"
HEAD   = "#2f2f2f"
SEL    = "#3d7fe0"
BORDER = "#3a3a3a"


def base_theme_apply():
    tm = ctk.ThemeManager.theme
    tm["CTkButton"].update(
        corner_radius = RADIUS,
        fg_color      = list(ACCENT),
        hover_color   = list(ACCENT_HOVER))
    tm["CTkEntry"].update(
        corner_radius = RADIUS,
        border_color  = list(BORDA))
    tm["CTkComboBox"].update(corner_radius = RADIUS)
    tm["CTkSwitch"].update(progress_color = list(ACCENT))
    tm["CTkToplevel"].update(fg_color = list(BG_CARD))


def centralize(window, parent, w, h):
    parent.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - h) // 3
    window.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")


def db_connect(path):
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    return connection


class Msg_Dialog(ctk.CTkToplevel):
    def __init__(self, master, title, texto, confirm=False, danger=False):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.result = False
        self.configure(fg_color=BG_CARD)
        centralize(self, master, 380, 170)

        ctk.CTkLabel(
            self, 
            text=title, 
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COR_TEXTO
            ).pack(anchor="w", padx=22, pady=(20, 4))
        ctk.CTkLabel(
            self, 
            text=texto, 
            text_color=COR_MUTED, 
            wraplength=336,
            justify="left"
            ).pack(anchor="w", padx=22)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=22, pady=18)
        if confirm:
            ctk.CTkButton(
                footer, 
                text="Cancelar", 
                width=90, 
                fg_color="transparent",
                border_width=1, 
                text_color=COR_TEXTO,
                hover_color=("#e5e7eb", "#333333"),
                command=lambda: self.close(False)
                ).pack(side="right", padx=8)
            ctk.CTkButton(
                footer, 
                text="Confirmar", 
                width=100,
                fg_color=DANGER if danger else ACCENT,
                hover_color=PERIGO_HOVER if danger else ACCENT_HOVER,
                command=lambda: self.close(True)
                ).pack(side="right")
        else:
            ctk.CTkButton(
                footer, 
                text="OK", 
                width=90, 
                fg_color=ACCENT,
                hover_color=ACCENT_HOVER,
                command=lambda: self.close(True)
                ).pack(side="right")
        self.bind("<Escape>", lambda e: self.close(False))
        self.after(120, self.grab_focus)
        self.wait_window(self)

    def grab_focus(self):
        try:
            self.grab_set()
            self.focus_force()
        except tk.TclError:
            pass

    def close(self, value):
        self.result = value
        self.destroy()


class Song_Edit_Dialog(ctk.CTkToplevel):
    def __init__(self, master, title, name="", link="", current_tags=None, all_tags=None):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.result = None

        # working copy of this song's tags — nothing touches the DB until Save
        self.tags = sorted(set(current_tags or []), key=str.lower)
        self.all_tags = sorted(set(all_tags or []), key=str.lower)

        self.configure(fg_color=BG_CARD)
        centralize(self, master, 460, 680)

        ctk.CTkLabel(
            self, 
            text       = title, 
            font       = ctk.CTkFont(size=18, weight="bold"),
            text_color = COR_TEXTO
            ).pack(anchor="w", padx=24, pady=(22, 10))
        
        # Name
        ctk.CTkLabel(
            self, 
            text       = "Nome", 
            text_color = COR_MUTED
            ).pack(anchor="w", padx=24)
        self.entry_name = ctk.CTkEntry(self, height=36, corner_radius=RADIUS)
        self.entry_name.pack(
            fill = "x", 
            padx = 24, 
            pady = (2, 10))
        if name:
            self.entry_name.insert(0, name)

        # Link
        ctk.CTkLabel(
            self, 
            text       = "Link (opcional)", 
            text_color = COR_MUTED
            ).pack(anchor="w", padx=24)
        self.entry_link = ctk.CTkEntry(
            self, 
            height           = 36, 
            corner_radius    = RADIUS,
            placeholder_text = "https://...")
        self.entry_link.pack(fill="x", padx=24, pady=(2, 0))
        if link:
            self.entry_link.insert(0, link)

        # Tags
        ctk.CTkLabel(
            self, 
            text       = "Tags", 
            text_color = COR_MUTED
            ).pack(anchor="w", pady = (8, 0), padx=24)
        line_add = ctk.CTkFrame(self, fg_color="transparent")
        line_add.pack(
            fill = "x", 
            padx = 24, 
            pady = (2, 6))
        
        # Drop-down
        self.combobox_tag = ctk.CTkComboBox(
            line_add, 
            values = self.all_tags, 
            height = 32)
        self.combobox_tag.set("")
        self.combobox_tag.pack(side="left", fill="x", expand = True)
        self.combobox_tag.bind("<Return>", lambda e: self.tag_add_and_stop(e))

        # Drop-down add
        ctk.CTkButton(
            line_add, 
            text    = "+", 
            width   = 36, 
            height  = 32,
            command = self.tag_add
            ).pack(side="left", padx=(6, 0))

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=24)
        self.list_tags = tk.Listbox(
            frame,
            height             = 6,
            selectmode         = "extended",
            exportselection    = False,
            bd                 = 0,
            highlightthickness = 0,
            activestyle        = "none",
            relief             = "flat",
            font               = ("", 12),
            bg                 = HEAD,
            fg                 = FG,
            selectbackground   = SEL,
            selectforeground   = "#ffffff")
        scroll_bar = ctk.CTkScrollbar(frame, command=self.list_tags.yview)
        self.list_tags.configure(yscrollcommand = scroll_bar.set)
        self.list_tags.pack(side = "left", fill = "both", expand=True)
        scroll_bar.pack(side = "left", fill = "y", padx = (4, 0))
        self.list_tags.bind("<Delete>", lambda e: self.tag_remove())
        ctk.CTkButton(
            self, 
            text        = "Remover", 
            width       = 100, 
            fg_color    = ACCENT,
            hover_color = ACCENT_HOVER, 
            command     = self.tag_remove
            ).pack(anchor="w", padx=24, pady=(4, 0))

        # Footer
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=24, pady=18)
        ctk.CTkButton(
            footer, 
            text        = "Salvar", 
            width       = 100, 
            fg_color    = ACCENT,
            hover_color = ACCENT_HOVER, 
            command     = self.save
            ).pack(side="right")
        ctk.CTkButton(
            footer, 
            text         = "Cancelar", 
            width        = 90, 
            fg_color     = "transparent",
            border_width = 1, 
            text_color   = COR_TEXTO,
            hover_color  = ("#e5e7eb", "#333333"),
            command      = self.destroy
            ).pack(side="right", padx=8)
        self.bind("<Return>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.destroy())
        self.after(120, self.grab_focus)
        self.tags_redraw()
        self.wait_window(self)

    def grab_focus(self):
        try:
            self.grab_set()
            self.entry_name.focus_set()
        except tk.TclError:
            pass

    def save(self):
        name = self.entry_name.get().strip()
        link = self.entry_link.get().strip() or None
        if not name:
            self.entry_name.configure(border_color=PERIGO)
            return
        self.result = (name, link, list(self.tags))
        self.destroy()

    def tags_redraw(self):
        self.list_tags.delete(0, "end")
        for name in self.tags:
            self.list_tags.insert("end", f" {name}")

    def tag_add(self):
        for name in self.combobox_tag.get().split(","):
            name = name.strip()
            if name and name.lower() not in {t.lower() for t in self.tags}:
                self.tags.append(name)
        self.tags.sort(key=str.lower)
        self.tags_redraw()
        self.combobox_tag.set("")
        self.combobox_tag.focus_set()
    
    def tag_add_and_stop(self, event):
        self.tag_add()
        return "break"

    def tag_remove(self):
        selected = set(self.list_tags.curselection())
        self.tags = [t for i, t in enumerate(self.tags) if i not in selected]
        self.tags_redraw()

    
class Tags_Table_New_Dialog(ctk.CTkToplevel):
    def __init__(self, master, title):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.result = None

        self.configure(fg_color=BG_CARD)
        centralize(self, master, 460, 200)

        ctk.CTkLabel(
            self, 
            text       = title, 
            font       = ctk.CTkFont(size=18, weight="bold"),
            text_color = COR_TEXTO
            ).pack(anchor="w", padx=24, pady=(22, 10))
        
        # Name
        ctk.CTkLabel(
            self, 
            text       = "Nome (ou múltiplos nomes separados por vírgula)", 
            text_color = COR_MUTED
            ).pack(anchor="w", padx=24)
        self.entry_tag_name = ctk.CTkEntry(self, height=36, corner_radius=RADIUS)
        self.entry_tag_name.pack(
            fill = "x", 
            padx = 24, 
            pady = (2, 10))

        # Footer
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=24, pady=18)
        ctk.CTkButton(
            footer, 
            text        = "Criar", 
            width       = 100, 
            fg_color    = ACCENT,
            hover_color = ACCENT_HOVER, 
            command     = self.save
            ).pack(side="right")
        ctk.CTkButton(
            footer, 
            text         = "Cancelar", 
            width        = 90, 
            fg_color     = "transparent",
            border_width = 1, 
            text_color   = COR_TEXTO,
            hover_color  = ("#e5e7eb", "#333333"),
            command      = self.destroy
            ).pack(side="right", padx=8)
        self.bind("<Return>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.destroy())
        self.after(120, self.grab_focus)
        self.wait_window(self)

    def grab_focus(self):
        try:
            self.grab_set()
            self.entry_tag_name.focus_set()
        except tk.TclError:
            pass

    def save(self):
        names = [
            name.strip()
            for name in self.entry_tag_name.get().split(",")
            if name.strip()
        ]
        if not names:
            self.entry_tag_name.configure(border_color=DANGER)
            return
        self.result = names
        self.destroy()


class Tags_Table_Edit_Dialog(ctk.CTkToplevel):
    def __init__(self, master, title, name):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.result = None

        self.configure(fg_color=BG_CARD)
        centralize(self, master, 460, 200)

        ctk.CTkLabel(
            self, 
            text       = title, 
            font       = ctk.CTkFont(size=18, weight="bold"),
            text_color = COR_TEXTO
            ).pack(anchor="w", padx=24, pady=(22, 10))
        
        # Name
        ctk.CTkLabel(
            self, 
            text       = "Nome", 
            text_color = COR_MUTED
            ).pack(anchor="w", padx=24)
        self.entry_tag_name = ctk.CTkEntry(self, height=36, corner_radius=RADIUS)
        self.entry_tag_name.pack(
            fill = "x", 
            padx = 24, 
            pady = (2, 10))
        self.entry_tag_name.insert(0, name)

        # Footer
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=24, pady=18)
        ctk.CTkButton(
            footer, 
            text        = "Atualizar", 
            width       = 100, 
            fg_color    = ACCENT,
            hover_color = ACCENT_HOVER, 
            command     = self.save
            ).pack(side="right")
        ctk.CTkButton(
            footer, 
            text         = "Cancelar", 
            width        = 90, 
            fg_color     = "transparent",
            border_width = 1, 
            text_color   = COR_TEXTO,
            hover_color  = ("#e5e7eb", "#333333"),
            command      = self.destroy
            ).pack(side="right", padx=8)
        self.bind("<Return>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.destroy())
        self.after(120, self.grab_focus)
        self.wait_window(self)

    def grab_focus(self):
        try:
            self.grab_set()
            self.entry_tag_name.focus_set()
        except tk.TclError:
            pass

    def save(self):
        name = self.entry_tag_name.get().strip()
        if not name or "," in name:
            self.entry_tag_name.configure(border_color=DANGER)
            return
        self.result = name
        self.destroy()


class App(ctk.CTk):
    def __init__(self, path):
        super().__init__(fg_color = BG_JANELA)
        
        base_theme_apply()

        self.title("Gerenciador de Músicas")

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        width  = 1440
        height = 720
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2

        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(900, 540)

        self.db_path = Path("")
        self.connection = None
        self.tags_ids_selected = []
        self.tags_table_ids = []
        self.font      = ctk.CTkFont(size=13)
        self.font_bold = ctk.CTkFont(size=13, weight="bold")

        self.db_open(path)
        self.ui_build()
        self.apply_theme()
        self.update_all()

    # ---------------------------------------------------------------- UI
    def card_create(self, parent):
        return ctk.CTkFrame(
            parent, 
            fg_color      = BG_CARD, 
            corner_radius = RADIUS_CARD,
            border_width  = 1, 
            border_color  = BORDA)

    def youtube_video_id(self, url):
        parsed = urlparse(url)
        if parsed.hostname in ("youtube.com", "www.youtube.com"):
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.hostname == "youtu.be":
            return parsed.path.lstrip("/").split("/")[0]
        return None
    
    def youtube_playlist_from_selected(self):
        video_ids = []

        for song_id in self.song_ids_selected():
            nome, url = self.connection.execute(
                "SELECT nome, link FROM musicas WHERE id = ?", 
                (song_id,)
                ).fetchone()

            video_id = self.youtube_video_id(url)
            if video_id:
                video_ids.append(video_id)

        if not video_ids:
            return

        url = (
            "https://www.youtube.com/watch_videos"
            "?video_ids=" + ",".join(video_ids)
        )

        webbrowser.open(url)

    def get_link_if_click_on_play_button(self, event):
        """Link of the ▶ cell under the mouse, or None."""
        if self.tree.identify_region(event.x, event.y) != "cell":
            return None
        if self.tree.identify_column(event.x) != PLAY_COLUMN:
            return None
        return self.song_links.get(self.tree.identify_row(event.y))

    def song_table_click(self, event):
        link = self.get_link_if_click_on_play_button(event)
        if link:
            if "://" not in link:          # tolerate "youtube.com/..." without scheme
                link = "https://" + link
            webbrowser.open(link)
            return "break"                 # don't change the row selection

    def song_table_hover(self, event):
        self.tree.configure(cursor="hand2" if self.get_link_if_click_on_play_button(event) else "")

    def song_table_double_click(self, event):
        if self.tree.identify_column(event.x) == PLAY_COLUMN:
            return "break"                 # double-clicking ▶ must not open the edit dialog
        self.song_edit()

    def ui_build(self):
        # ---------------- top
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(16, 8))
        ctk.CTkLabel(
            top,
            text       = f"🎵  {self.db_path}",
            font       = ctk.CTkFont(size=30, weight="normal"),
            text_color = COR_TEXTO
            ).pack(side="left")
        ctk.CTkButton(
            top, 
            text         = "Abrir database...", 
            width        = 110, 
            fg_color     = "transparent",
            border_width = 1, 
            text_color   = COR_TEXTO,
            hover_color  = ("#e5e7eb", "#333333"),
            command      = self.db_open_from_file_system_dialog
            ).pack(side="right")

        # ---------------- tabs
        tab_buttons_bar = ctk.CTkFrame(
            self,
            fg_color      = "transparent",
            corner_radius = 12,
            height        = 48)
        tab_buttons_bar.pack(
            fill = "x",
            padx = 18,
            pady = (20, 0))

        # Tags Buttons
        songs_button = ctk.CTkButton(
            tab_buttons_bar,
            text          = "Songs",
            height        = 36,
            width         = 100,
            corner_radius = 10,
            fg_color      = ACCENT,
            hover_color   = ACCENT_HOVER,
            text_color    = COR_TEXTO,)
        songs_button.pack(
            side = "left",
            padx = (0, 6),)
        tags_button = ctk.CTkButton(
            tab_buttons_bar,
            text          = "Tags",
            height        = 36,
            width         = 100,
            corner_radius = 10,
            fg_color      = BG_CARD,
            # hover_color=BG_HOVER,
            text_color    = COR_TEXTO,)
        tags_button.pack(
            side="left",)

        # Tab Content
        tab_content = ctk.CTkFrame(
            self,
            fg_color="transparent")
        tab_content.pack(
            fill   = "both",
            expand = True,
            padx   = 20,
            pady   = (8, 20))

        songs_tab_content = ctk.CTkFrame(
            tab_content,
            fg_color = "transparent")
        songs_tab_content.grid_rowconfigure(0,    weight=1)
        songs_tab_content.grid_columnconfigure(0, weight=1)
        
        tags_tab_content = ctk.CTkFrame(
            tab_content,
            fg_color = "transparent")
        tags_tab_content.grid_rowconfigure(0,    weight=1)
        tags_tab_content.grid_columnconfigure(1, weight=1)

        def show_tab_content(name):
            songs_tab_content.pack_forget()
            tags_tab_content.pack_forget()
            songs_button.configure(
                fg_color = ACCENT if name == "Songs" else BG_CARD)
            tags_button.configure(
                fg_color = ACCENT if name == "Tags"  else BG_CARD)
            if name == "Songs":
                songs_tab_content.pack(fill = "both", expand = True)
            else:
                tags_tab_content.pack(fill  = "both", expand = True)

        songs_button.configure(command = lambda: show_tab_content("Songs"))
        tags_button.configure(command  = lambda: show_tab_content("Tags"))
        show_tab_content("Songs")

        # ---------------- tabs -> songs_panel
        songs_panel = self.card_create(songs_tab_content)
        songs_panel.grid(
            row    = 0, 
            column = 0, 
            sticky = "nsew")
        songs_panel.grid_rowconfigure(0,    weight = 0)  # header
        songs_panel.grid_rowconfigure(1,    weight = 1)  # area takes remaining space
        songs_panel.grid_rowconfigure(2,    weight = 0)  # footer
        songs_panel.grid_columnconfigure(0, weight = 1)

        # ---------------- tabs -> songs_panel -> header
        header = ctk.CTkFrame(
            songs_panel, 
            fg_color = "transparent")
        header.grid(
            row    = 0,
            column = 0,
            sticky = "ew", 
            padx   = 16, 
            pady   = (16, 10))
        ctk.CTkButton(
            header, 
            text        = "＋  Nova música", 
            height      = 36, 
            fg_color    = ACCENT,
            hover_color = ACCENT_HOVER, 
            font        = self.font_bold,
            command     = self.song_new
            ).pack(side="left")
        ctk.CTkButton(
            header, 
            text         = "Editar", 
            height       = 36, 
            width        = 80, 
            fg_color     = "transparent",
            border_width = 1, 
            text_color   = COR_TEXTO,
            hover_color  = ("#e5e7eb", "#333333"),
            command      = self.song_edit
            ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            header, 
            text         = "Excluir", 
            height       = 36, 
            width        = 80, 
            fg_color     = "transparent",
            border_width = 1, 
            border_color = DANGER, 
            text_color   = DANGER,
            hover_color  = ("#fee2e2", "#3b1a1a"),
            command      = self.song_delete
            ).pack(side="left", padx=(8, 8))
        
        # Search bar
        self.entry_search = ctk.CTkEntry(
            header,
            height           = 36, 
            corner_radius    = RADIUS,
            placeholder_text = "🔍  Buscas ou query via 'tag:'")
        self.entry_search.pack(side="left", fill="x", expand=True)
        self.entry_search.bind("<KeyRelease>", lambda e: self.songs_table_update())

        self.youtube_playlist_button = ctk.CTkButton(
            header,
            text    = "Create YouTube Playlist",
            height  = 36, 
            command = self.youtube_playlist_from_selected
        )
        self.youtube_playlist_button.pack(side="left", padx=(14, 0))

        # ---------------- songs_panel -> table
        # Area
        area = tk.Frame(
            songs_panel, 
            bd                 = 0, 
            highlightthickness = 0)
        area.grid(
            row    = 1, 
            column = 0, 
            sticky = "nsew",
            padx   =  (16, 8), 
            pady   =  0)
        area.grid_rowconfigure(0, weight=1)
        area.grid_columnconfigure(0, weight=1)
        self.tree_area = area

        # Columns
        self.tree = ttk.Treeview(
            area,
            columns    = ("play", "nome", "tags"),
            show       = "headings",
            selectmode = "extended",
            style      = "Moderno.Treeview")
        self.tree.heading("play", text = "",       anchor = "center")
        self.tree.heading("nome", text = "Música", anchor = "w")
        self.tree.heading("tags", text = "Tags",   anchor = "w")
        self.tree.column("play",  width = 48,      minwidth = 48, stretch = False, anchor = "center")
        self.tree.column("nome",  width = 280,     anchor = "w")
        self.tree.column("tags",  width = 240,     anchor = "w")

        # Scrollbar
        scroll_bar = ctk.CTkScrollbar(
            songs_panel, 
            command=self.tree.yview)
        self.tree.configure(yscrollcommand = scroll_bar.set)
        self.tree.grid(in_ = area, row = 0, column = 0, sticky="nsew") # stretch toward all four sides
        scroll_bar.grid(row=1, column=1, sticky="ns", padx=(0, 8))

        # Events
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.songs_table_update_selected())
        self.tree.bind("<Button-1>",         self.song_table_click)
        self.tree.bind("<Motion>",           self.song_table_hover)
        self.tree.bind("<Double-1>",         self.song_table_double_click)
        self.tree.bind("<Delete>",           lambda e: self.song_delete())

        # ---------------- songs_panel -> footer
        footer = ctk.CTkFrame(
            songs_panel,
            fg_color = "transparent")
        footer.grid(
            row        = 2, 
            column     = 0, 
            columnspan = 2,
            sticky     = "ew",
            padx       = 16,
            pady       = 8)
        self.songs_stats_label = ctk.CTkLabel(
            footer, 
            text       = "", 
            text_color = COR_MUTED)
        self.songs_stats_label.pack(side="right")

        # ---------------- tags_panel -> tags
        tags_panel = self.card_create(tags_tab_content)
        tags_panel.grid(
            row    = 0, 
            column = 1, 
            sticky = "nsew", 
            padx   = (0, 0),
            pady   = (0, 0))
        
        # To control padding for everything
        internal = ctk.CTkFrame(
            tags_panel, 
            fg_color = "transparent")
        internal.pack(
            fill   = "both",
            expand = True, 
            padx   = 16, 
            pady   = (8, 16))
        internal.grid_columnconfigure(0, weight = 1)
        internal.grid_rowconfigure(1,    weight = 1) # 1 = list

        tags_header = ctk.CTkFrame(
            internal, 
            fg_color = "transparent")
        tags_header.grid(
            row    = 0,
            column = 0,
            sticky = "ew", 
            pady   = (8, 10))
        ctk.CTkButton(
            tags_header, 
            text        = "＋  Nova tag", 
            height      = 36, 
            fg_color    = ACCENT,
            hover_color = ACCENT_HOVER, 
            font        = self.font_bold,
            command     = self.tags_table_new_tag
            ).pack(side="left")
        ctk.CTkButton(
            tags_header, 
            text         = "Editar", 
            height       = 36, 
            width        = 80, 
            fg_color     = "transparent",
            border_width = 1, 
            text_color   = COR_TEXTO,
            hover_color  = ("#e5e7eb", "#333333"),
            command      = self.tags_table_edit
            ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            tags_header, 
            text         = "Excluir", 
            height       = 36, 
            width        = 80, 
            fg_color     = "transparent",
            border_width = 1, 
            border_color = DANGER, 
            text_color   = DANGER,
            hover_color  = ("#fee2e2", "#3b1a1a"),
            command      = self.tags_table_delete
            ).pack(side="left", padx=(8, 8))

        frame2 = ctk.CTkFrame(internal, fg_color="transparent")
        frame2.grid(
            row    = 1,
            column = 0,
            sticky = "nsew",
            padx   = 48,
            pady   = (4, 0))

        self.tags_table_list = ttk.Treeview(
            frame2, 
            columns    = ("tag",), 
            show       = "", # hides the header
            selectmode = "extended", 
            style      = "Moderno.Treeview")
        self.tags_table_list.heading("tag", text="", anchor="w")
        self.tags_table_list.column("tag", anchor="w")
        scroll_bar = ctk.CTkScrollbar(frame2, command=self.tags_table_list.yview)
        self.tags_table_list.configure(yscrollcommand=scroll_bar.set)
        self.tags_table_list.pack(side="left", fill="both", expand=True)
        self.tags_table_list.bind("<Double-1>", lambda e: self.tags_table_edit())
        scroll_bar.pack(side="left", fill="y", padx=(4, 0))


    def apply_theme(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Moderno.Treeview", 
            background=BG, 
            fieldbackground=BG,
            foreground=FG, 
            rowheight=34, 
            borderwidth=0,
            relief="flat", 
            font=("", 12))
        style.configure(
            "Moderno.Treeview.Heading", 
            background=HEAD, 
            foreground=FG,
            relief="flat", 
            borderwidth=0, 
            padding=(10, 8), 
            font=("", 11, "bold"))
        style.map(
            "Moderno.Treeview.Heading", 
            background=[("active", HEAD)])
        style.map(
            "Moderno.Treeview", 
            background=[("selected", SEL)],
            foreground=[("selected", "#ffffff")])
        style.layout(
            "Moderno.Treeview", 
            [
                ("Treeview.treearea", {"sticky": "nswe"})
            ])
        self.tree_area.configure(bg=BG)

    # ------------------------------------------------------------- Database
    def db_open_from_file_system_dialog(self):
        path = get_db_from_file_system()
        if path:
            self.db_open(path)

    def db_open(self, path):
        path = (path or "").strip()
        if not path:
            self.title(f"Gerenciador de Músicas - Sem database")
            return
        try:
            novo = db_connect(path)
        except sqlite3.Error as ex:
            Msg_Dialog(self, "Erro", f"Não foi possível abrir o banco:\n{ex}")
            return
        if self.connection:
            self.connection.close()
        self.connection = novo
        self.db_path = Path(path)
        self.title(f"Gerenciador de Músicas - {self.db_path.name}")


    # ------------------------------------------------------- Updates
    def update_all(self):
        self.songs_table_update()
        self.tags_table_update()

    def song_ids_selected(self):
        return [int(i) for i in self.tree.selection()]

    def parse_search(self, texto):
        """
        tag:x           -> must have tag x
        tag:x,y         -> must have x AND y (comma = AND)
        tag:x|y         -> must have x OR y  (pipe = OR, within one group)
        -tag:x / !tag:x -> must NOT have tag x
        anything else   -> free text (song name or tag substring)
        """
        included_tags = []   # each item is a list of tag names; ANY in the list satisfies that group
        excluded_tags = []
        free_text = []
        for token in texto.split():
            low = token.lower()
            if low.startswith("!tag:"):
                value = token[5:]
                names = [n.strip() for n in value.split("|") if n.strip()]
                excluded_tags.extend(names)
            elif low.startswith("tag:"):
                value = token[4:]

                # split into AND-groups by comma; each group may itself be an OR via "|"
                for part in value.split(","):
                    names = [n.strip() for n in part.split("|") if n.strip()]
                    if names:
                        included_tags.append(names)
            else:
                free_text.append(token)
        return included_tags, excluded_tags, " ".join(free_text)

    def songs_table_update(self):
        if not self.connection:
            return
        
        # Stored previously selected entries
        selected = set(self.tree.selection())

        # Query the db
        included_tags, excluded_tags, free_text = self.parse_search(self.entry_search.get())
        search = f"%{free_text.strip()}%"
        params = [search, search]
        sql = """
            SELECT m.id, m.nome, COALESCE(GROUP_CONCAT(t.nome, ', '), ''), COUNT(t.id), m.link
            FROM musicas m
            LEFT JOIN musicas_tags mt ON mt.musica_id = m.id
            LEFT JOIN tags t ON t.id = mt.tag_id
            WHERE (m.nome LIKE ? OR EXISTS (
                SELECT 1 FROM musicas_tags x JOIN tags y ON y.id = x.tag_id
                WHERE x.musica_id = m.id AND y.nome LIKE ?))
            """

        # each group: song must have at least one tag from this group (OR inside),
        # and this must hold for every group (AND across groups)
        for group in included_tags:
            marcas = ",".join("?" * len(group))
            sql += f"""
                AND EXISTS (
                    SELECT 1 FROM musicas_tags mt2 JOIN tags t2 ON t2.id = mt2.tag_id
                    WHERE mt2.musica_id = m.id AND t2.nome COLLATE NOCASE IN ({marcas})
                )
                """
            params.extend(group)

        # excluded tags: song must NOT have any of these
        if excluded_tags:
            marcas = ",".join("?" * len(excluded_tags))
            sql += f"""
                AND NOT EXISTS (
                    SELECT 1 FROM musicas_tags mt3 JOIN tags t3 ON t3.id = mt3.tag_id
                    WHERE mt3.musica_id = m.id AND t3.nome COLLATE NOCASE IN ({marcas})
                )
                """
            params.extend(excluir)

        sql += " GROUP BY m.id"
        sql += " ORDER BY m.nome COLLATE NOCASE"

        rows = self.connection.execute(sql, params).fetchall()

        # Delete every existing row from the table.
        self.tree.delete(*self.tree.get_children())

        # Fill the table
        self.song_links = {}
        self.tree.delete(*self.tree.get_children())
        for mid, nome, tags, _, link in rows:
            self.song_links[str(mid)] = link
            self.tree.insert(
                "", 
                "end", 
                iid=str(mid),
                values=("▶" if link else "", nome, tags))
        keep = [i for i in selected if self.tree.exists(i)]
        if keep:
            self.tree.selection_set(keep)
        
        # Count the total of songs_panel (selected/total)
        total = self.connection.execute("SELECT COUNT(*) FROM musicas").fetchone()[0]
        self.songs_stats_label.configure(text=f"Exibindo {len(rows)} de {total} música(s)")

        # update
        self.songs_table_update_selected()

    def songs_table_update_selected(self):
        ids = self.song_ids_selected()

        self.tags_ids_selected = []

        if not ids:
            return

        marcas = ",".join("?" * len(ids))

        rows = self.connection.execute(
            f"""
            SELECT t.id, t.nome, COUNT(*)
            FROM musicas_tags mt
            JOIN tags t ON t.id = mt.tag_id
            WHERE mt.musica_id IN ({marcas})
            GROUP BY t.id
            ORDER BY t.nome COLLATE NOCASE
            """, 
            ids
            ).fetchall()

        for tag_id, nome, qtd in rows:
            self.tags_ids_selected.append(tag_id)
            texto = f"{nome}" if len(ids) == 1 else f"{nome}   ({qtd}/{len(ids)})"

    def song_new(self):
        song_edit_dialog = Song_Edit_Dialog(
            self, 
            "Nova música")
        if not song_edit_dialog.result:
            return
        nome, link = song_edit_dialog.result
        try:
            cur = self.connection.execute(
                "INSERT INTO musicas(nome, link) VALUES (?, ?)", 
                (nome, link))
            self.connection.commit()
        except sqlite3.IntegrityError:
            Msg_Dialog(
                self, 
                "Já existe", 
                "Já existe uma música com esse nome ou link.")
            return
        self.entry_search.set("")
        self.songs_table_update()
        iid = str(cur.lastrowid)
        if self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.see(iid)
        self.combobox_tag.focus_set()

    def song_edit(self):
        ids = self.song_ids_selected()
        if len(ids) != 1:
            return
        song_id = ids[0]
        nome, link = self.connection.execute(
            "SELECT nome, link FROM musicas WHERE id = ?", 
            (song_id,)
            ).fetchone()
        current_tags = [r[0] for r in self.connection.execute(
            "SELECT t.nome FROM musicas_tags mt JOIN tags t ON t.id = mt.tag_id "
            "WHERE mt.musica_id = ? ORDER BY t.nome COLLATE NOCASE",
            (song_id,)).fetchall()]
        all_tags = [r[0] for r in self.connection.execute(
            "SELECT nome FROM tags ORDER BY nome COLLATE NOCASE").fetchall()]
        song_edit_dialog = Song_Edit_Dialog(
            self, 
            "Editar música",
            nome, 
            link, 
            current_tags, 
            all_tags)
        if not song_edit_dialog.result:
            return
        nome, link, final_tags = song_edit_dialog.result
        try:
            self.connection.execute(
                "UPDATE musicas SET nome = ?, link = ? WHERE id = ?",
                (nome, link, song_id))
        except sqlite3.IntegrityError:
            self.connection.rollback()
            Msg_Dialog(
                self, 
                "Já existe", 
                "Já existe uma música com esse nome ou link.")
            return

        current_tags_lower = {t.lower(): t for t in current_tags}
        final_tags_lower = {t.lower(): t for t in final_tags}

        # remove tags that were dropped
        to_remove = set(current_tags_lower) - set(final_tags_lower)
        if to_remove:
            ids_to_remove = [self.tags_table_get_or_add(current_tags_lower[k]) for k in to_remove]
            self.connection.executemany(
                "DELETE FROM musicas_tags WHERE musica_id = ? AND tag_id = ?",
                [(song_id, tid) for tid in ids_to_remove])

        # add tags that are new (get_or_create makes new tag rows as needed)
        to_add = set(final_tags_lower) - set(current_tags_lower)
        if to_add:
            ids_to_add = [self.tags_table_get_or_add(final_tags_lower[k]) for k in to_add]
            self.connection.executemany(
                "INSERT OR IGNORE INTO musicas_tags(musica_id, tag_id) VALUES (?, ?)",
                [(song_id, tid) for tid in ids_to_add])

        self.connection.commit()
        self.songs_table_update()

    def song_delete(self):
        ids = self.song_ids_selected()
        if not ids:
            return
        if not Msg_Dialog(
            self, 
            "Excluir música(s)", 
            f"Excluir {len(ids)} música(s)? "
            "Essa ação não pode ser desfeita.", 
            confirm=True, 
            danger=True
            ).result:
            return
        self.connection.executemany(
            "DELETE FROM musicas WHERE id = ?", 
            [(i,) for i in ids])
        self.connection.commit()
        self.update_all()


    def tags_table_ids_from_list_selected(self):
        return [int(i) for i in self.tags_table_list.selection()]

    def tags_table_update(self):
        rows = self.connection.execute(
            """
            SELECT t.id, t.nome, COUNT(mt.musica_id)
            FROM tags t LEFT JOIN musicas_tags mt ON mt.tag_id = t.id
            GROUP BY t.id ORDER BY t.nome COLLATE NOCASE
            """
            ).fetchall()
        self.tags_table_list.delete(*self.tags_table_list.get_children())
        for tid, nome, qtd in rows:
            self.tags_table_list.insert("", "end", iid=str(tid), values=(f"{nome}   ({qtd})",))

    def tags_table_new_tag(self):
        tags_table_new = Tags_Table_New_Dialog(
            self, 
            "Nova tag")
        if not tags_table_new.result:
            return
        names = tags_table_new.result
        for n in names:
            self.tags_table_get_or_add(n)
        self.connection.commit()
        self.tags_table_update()

    def tags_table_get_or_add(self, nome):
        row = self.connection.execute(
            "SELECT id FROM tags WHERE nome = ? COLLATE NOCASE", 
            (nome,)
            ).fetchone()
        if row:
            return row[0]
        return self.connection.execute("INSERT INTO tags(nome) VALUES (?)", (nome,)).lastrowid

    def tags_table_edit(self):
        ids = self.tags_table_ids_from_list_selected()
        if len(ids) != 1:
            return
        tag_id = ids[0]

        row = self.connection.execute(
            "SELECT nome FROM tags WHERE id = ?",
            (tag_id,)
            ).fetchone()
        if row is None:
            return
        name = row[0]

        tags_table_edit = Tags_Table_Edit_Dialog(
            self,
            "Editar tag",
            name)
        if not tags_table_edit.result:
            return
        new_name = tags_table_edit.result.strip()
        if not new_name or "," in new_name:
            return
        try:
            self.connection.execute(
                "UPDATE tags SET nome = ? WHERE id = ?",
                (new_name, tag_id),
            )
            self.connection.commit()
        except sqlite3.IntegrityError:
            self.connection.rollback()
            Msg_Dialog(
                self, 
                "Já existe", 
                "Já existe uma tag com esse nome.")
            return

        self.update_all()

    def tags_table_delete(self):
        ids = self.tags_table_ids_from_list_selected()
        if not ids:
            return
        if not Msg_Dialog(
            self,
            "Excluir tag(s)",
            f"Excluir {len(ids)} tag(s) do banco? "
            "Elas serão removidas de todas as músicas.",
            confirm=True,
            danger=True
            ).result:
            return
        self.connection.executemany(
            "DELETE FROM tags WHERE id = ?",
            [(tid,) for tid in ids])
        self.connection.commit()
        self.update_all()

def get_db_from_file_system():
    return filedialog.asksaveasfilename(
            title="Abrir ou criar banco SQLite", defaultextension=".db",
            filetypes=[("SQLite", "*.db *.sqlite *.sqlite3"), ("Todos", "*.*")],
            confirmoverwrite=False)

def get_database_in_exec_folder():
    if getattr(sys, "frozen", False):
        # running as a PyInstaller exe — use the folder containing the exe itself
        base = Path(sys.executable).parent
    else:
        # running as a normal .py script
        base = Path(__file__).parent
    dbs_found = sorted(base.glob("*.db"))
    if dbs_found:
        return dbs_found[0]
    return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        db_in_exec_folder = get_database_in_exec_folder()
        path = str(db_in_exec_folder) if db_in_exec_folder else get_db_from_file_system()
    App(path).mainloop()
