import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import fitz
from deep_translator import GoogleTranslator
from langdetect import detect
import threading
import sys
import os

# ─────────────────────────────────────────
#  Utilitários
# ─────────────────────────────────────────

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


IDIOMAS = {
    "Português (Brasil)": "pt",
    "English":            "en",
    "Español":            "es",
    "Français":           "fr",
    "Deutsch":            "de",
}

NOMES_IDIOMA = {
    "pt": "Português",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "it": "Italiano",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "ru": "Russian",
}

# ─────────────────────────────────────────
#  Estado Global
# ─────────────────────────────────────────

pdf_original   = None
texto_extraido = ""
cache_traducao = {}

# ─────────────────────────────────────────
#  Lógica
# ─────────────────────────────────────────

def abrir_pdf():
    global pdf_original, texto_extraido

    caminho = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    if not caminho:
        return

    try:
        pdf_original   = fitz.open(caminho)
        texto_extraido = ""

        for pagina in pdf_original:
            blocos = pagina.get_text("blocks")
            for bloco in blocos:
                # bloco = (x0, y0, x1, y1, text, block_no, block_type)
                # block_type 1 = imagem → ignorar
                if len(bloco) >= 7 and bloco[6] == 1:
                    continue
                texto = bloco[4] if len(bloco) > 4 else ""
                texto_extraido += texto

        if not texto_extraido.strip():
            messagebox.showwarning(
                "Aviso",
                "Nenhum texto encontrado. O PDF pode ser escaneado (imagem) e não possui camada de texto."
            )
            return

        # Atualiza área de texto original
        txt_original.config(state="normal")
        txt_original.delete(1.0, tk.END)
        txt_original.insert(tk.END, texto_extraido)
        txt_original.config(state="disabled")

        # Limpa tradução anterior
        txt_traducao.config(state="normal")
        txt_traducao.delete(1.0, tk.END)
        txt_traducao.config(state="disabled")

        # Detecta idioma
        try:
            codigo = detect(texto_extraido)
            nome   = NOMES_IDIOMA.get(codigo, codigo.upper())
        except Exception:
            codigo = "?"
            nome   = "Desconhecido"

        lbl_idioma.config(text=f"Idioma detectado: {nome}")
        nome_arquivo = os.path.basename(caminho)
        lbl_arquivo.config(text=f"📄  {nome_arquivo}")
        btn_traduzir.config(state="normal")
        btn_salvar.config(state="disabled")
        set_status("PDF carregado com sucesso.")

    except Exception as e:
        messagebox.showerror("Erro ao abrir PDF", str(e))


def _traduzir_worker():
    destino_nome  = combo_idioma.get()
    destino_codigo = IDIOMAS[destino_nome]

    btn_traduzir.config(state="disabled")
    btn_salvar.config(state="disabled")
    progress.start(10)
    set_status("Traduzindo… aguarde.")

    try:
        # Divide o texto em blocos de até 4500 chars (limite do GoogleTranslator)
        LIMITE = 4500
        partes = [texto_extraido[i:i+LIMITE]
                  for i in range(0, len(texto_extraido), LIMITE)]

        resultado = []
        for parte in partes:
            if parte.strip():
                chave = (parte, destino_codigo)
                if chave in cache_traducao:
                    resultado.append(cache_traducao[chave])
                else:
                    trad = GoogleTranslator(source="auto", target=destino_codigo).translate(parte)
                    cache_traducao[chave] = trad
                    resultado.append(trad)

        traducao_completa = "\n".join(resultado)

        txt_traducao.config(state="normal")
        txt_traducao.delete(1.0, tk.END)
        txt_traducao.insert(tk.END, traducao_completa)
        txt_traducao.config(state="disabled")

        set_status("Tradução concluída!")
        btn_salvar.config(state="normal")

    except Exception as e:
        messagebox.showerror("Erro na tradução", str(e))
        set_status("Erro na tradução.")

    finally:
        progress.stop()
        progress["value"] = 0
        btn_traduzir.config(state="normal")


def traduzir_thread():
    if not texto_extraido.strip():
        messagebox.showwarning("Aviso", "Nenhum texto para traduzir. Abra um PDF primeiro.")
        return
    threading.Thread(target=_traduzir_worker, daemon=True).start()


def traduzir_bloco(texto, destino):
    chave = (texto, destino)
    if chave in cache_traducao:
        return cache_traducao[chave]
    try:
        trad = GoogleTranslator(source="auto", target=destino).translate(texto)
        cache_traducao[chave] = trad
        return trad
    except Exception:
        return texto


def salvar_pdf():
    if not pdf_original:
        return

    caminho = filedialog.asksaveasfilename(
        defaultextension=".pdf",
        filetypes=[("PDF files", "*.pdf")]
    )
    if not caminho:
        return

    destino_codigo = IDIOMAS[combo_idioma.get()]

    def _salvar_worker():
        btn_salvar.config(state="disabled")
        progress.start(10)
        set_status("Salvando PDF traduzido…")

        try:
            novo_pdf = fitz.open()

            for pagina in pdf_original:
                nova = novo_pdf.new_page(
                    width=pagina.rect.width,
                    height=pagina.rect.height
                )
                blocos = pagina.get_text("blocks")

                for bloco in blocos:
                    if len(bloco) >= 7 and bloco[6] == 1:
                        # Imagem – copia sem traduzir
                        continue
                    x0, y0 = bloco[0], bloco[1]
                    texto   = bloco[4] if len(bloco) > 4 else ""
                    if texto.strip():
                        trad = traduzir_bloco(texto, destino_codigo)
                        nova.insert_text((x0, y0), trad, fontsize=10)

            novo_pdf.save(caminho)
            messagebox.showinfo("Sucesso", "PDF traduzido salvo com sucesso!")
            set_status("PDF salvo.")

        except Exception as e:
            messagebox.showerror("Erro ao salvar", str(e))
            set_status("Erro ao salvar PDF.")

        finally:
            progress.stop()
            progress["value"] = 0
            btn_salvar.config(state="normal")

    threading.Thread(target=_salvar_worker, daemon=True).start()


def set_status(msg):
    lbl_status.config(text=msg)


# ─────────────────────────────────────────
#  Interface
# ─────────────────────────────────────────

COR_BG       = "#0f0f13"
COR_PAINEL   = "#1a1a24"
COR_BORDA    = "#2a2a3a"
COR_ACCENT   = "#7c5cfc"
COR_ACCENT2  = "#a78bfa"
COR_TEXTO    = "#e8e8f0"
COR_SUBTEXTO = "#888899"
COR_SUCESSO  = "#4ade80"
FONTE_UI     = ("Segoe UI", 10)
FONTE_MONO   = ("Consolas", 10)
FONTE_TITULO = ("Segoe UI Semibold", 13)

janela = tk.Tk()
janela.title("PolyPDF — Tradutor de PDFs")
janela.geometry("1020x760")
janela.minsize(800, 600)
janela.configure(bg=COR_BG)

# Ícone (ignora se não encontrar)
try:
    janela.iconbitmap(resource_path("icon.ico"))
except Exception:
    pass

# ── Cabeçalho ──────────────────────────────────────────────
frame_header = tk.Frame(janela, bg=COR_BG)
frame_header.pack(fill="x", padx=24, pady=(20, 0))

tk.Label(
    frame_header,
    text="PolyPDF",
    font=("Segoe UI Semibold", 22),
    fg=COR_ACCENT2,
    bg=COR_BG
).pack(side="left")

tk.Label(
    frame_header,
    text="  Tradutor Inteligente de PDFs",
    font=("Segoe UI", 12),
    fg=COR_SUBTEXTO,
    bg=COR_BG
).pack(side="left", pady=6)

# ── Barra de controles ─────────────────────────────────────
frame_ctrl = tk.Frame(janela, bg=COR_PAINEL, pady=14)
frame_ctrl.pack(fill="x", padx=24, pady=14)

# Estilo comum de botão
def make_btn(parent, text, cmd, color=COR_ACCENT):
    return tk.Button(
        parent,
        text=text,
        command=cmd,
        bg=color,
        fg="white",
        activebackground=COR_ACCENT2,
        activeforeground="white",
        relief="flat",
        bd=0,
        font=("Segoe UI Semibold", 10),
        padx=18,
        pady=8,
        cursor="hand2",
    )

btn_abrir = make_btn(frame_ctrl, "📂  Abrir PDF", abrir_pdf)
btn_abrir.pack(side="left", padx=(16, 6))

tk.Label(frame_ctrl, text="Traduzir para:", fg=COR_SUBTEXTO,
         bg=COR_PAINEL, font=FONTE_UI).pack(side="left", padx=(14, 4))

style = ttk.Style()
style.theme_use("clam")
style.configure(
    "Custom.TCombobox",
    fieldbackground=COR_BORDA,
    background=COR_BORDA,
    foreground=COR_TEXTO,
    selectbackground=COR_ACCENT,
    selectforeground="white",
    bordercolor=COR_BORDA,
    arrowcolor=COR_ACCENT2,
)

combo_idioma = ttk.Combobox(
    frame_ctrl,
    values=list(IDIOMAS.keys()),
    state="readonly",
    width=20,
    style="Custom.TCombobox",
    font=FONTE_UI,
)
combo_idioma.set("Português (Brasil)")
combo_idioma.pack(side="left", padx=4)

btn_traduzir = make_btn(frame_ctrl, "⚡  Traduzir", traduzir_thread)
btn_traduzir.pack(side="left", padx=10)
btn_traduzir.config(state="disabled")

btn_salvar = make_btn(frame_ctrl, "💾  Salvar PDF", salvar_pdf, color="#22c55e")
btn_salvar.pack(side="left", padx=4)
btn_salvar.config(state="disabled")

# ── Info arquivo e idioma ──────────────────────────────────
frame_info = tk.Frame(janela, bg=COR_BG)
frame_info.pack(fill="x", padx=24)

lbl_arquivo = tk.Label(
    frame_info, text="Nenhum arquivo aberto",
    fg=COR_SUBTEXTO, bg=COR_BG, font=FONTE_UI, anchor="w"
)
lbl_arquivo.pack(side="left")

lbl_idioma = tk.Label(
    frame_info, text="Idioma detectado: —",
    fg=COR_ACCENT2, bg=COR_BG, font=("Segoe UI Semibold", 10), anchor="e"
)
lbl_idioma.pack(side="right")

# ── Área de textos ─────────────────────────────────────────
frame_textos = tk.Frame(janela, bg=COR_BG)
frame_textos.pack(fill="both", expand=True, padx=24, pady=12)
frame_textos.columnconfigure(0, weight=1)
frame_textos.columnconfigure(1, weight=1)
frame_textos.rowconfigure(1, weight=1)

def make_label_coluna(parent, texto, col):
    tk.Label(
        parent, text=texto,
        fg=COR_SUBTEXTO, bg=COR_BG,
        font=("Segoe UI Semibold", 9),
        anchor="w"
    ).grid(row=0, column=col, sticky="w", padx=(0 if col == 0 else 8, 0), pady=(0, 4))

make_label_coluna(frame_textos, "TEXTO ORIGINAL", 0)
make_label_coluna(frame_textos, "TRADUÇÃO", 1)

def make_text_area(parent, row, col):
    frm = tk.Frame(parent, bg=COR_BORDA, bd=1)
    frm.grid(row=row, column=col, sticky="nsew",
             padx=(0 if col == 0 else 8, 0), pady=0)
    frm.rowconfigure(0, weight=1)
    frm.columnconfigure(0, weight=1)

    txt = tk.Text(
        frm,
        wrap="word",
        bg=COR_PAINEL,
        fg=COR_TEXTO,
        insertbackground=COR_ACCENT2,
        selectbackground=COR_ACCENT,
        relief="flat",
        bd=0,
        font=FONTE_MONO,
        padx=12,
        pady=12,
    )
    sb = tk.Scrollbar(frm, command=txt.yview, bg=COR_BORDA,
                      troughcolor=COR_PAINEL, relief="flat")
    txt.config(yscrollcommand=sb.set)
    txt.grid(row=0, column=0, sticky="nsew")
    sb.grid(row=0, column=1, sticky="ns")
    return txt

txt_original  = make_text_area(frame_textos, 1, 0)
txt_traducao  = make_text_area(frame_textos, 1, 1)
txt_original.config(state="disabled")
txt_traducao.config(state="disabled")

# ── Rodapé: progresso + status ─────────────────────────────
frame_footer = tk.Frame(janela, bg=COR_PAINEL, pady=10)
frame_footer.pack(fill="x", padx=24, pady=(0, 16))

lbl_status = tk.Label(
    frame_footer,
    text="Pronto. Abra um PDF para começar.",
    fg=COR_SUBTEXTO,
    bg=COR_PAINEL,
    font=FONTE_UI,
    anchor="w"
)
lbl_status.pack(side="left", padx=14)

style.configure(
    "dark.Horizontal.TProgressbar",
    troughcolor=COR_BORDA,
    background=COR_ACCENT,
    bordercolor=COR_BORDA,
    lightcolor=COR_ACCENT,
    darkcolor=COR_ACCENT,
)
progress = ttk.Progressbar(
    frame_footer,
    mode="indeterminate",
    length=180,
    style="dark.Horizontal.TProgressbar"
)
progress.pack(side="right", padx=14)

# ── Loop principal ─────────────────────────────────────────
janela.mainloop()