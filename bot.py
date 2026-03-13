import os
import discord
import json
import random
import string
import time 
from dotenv import load_dotenv
from discord.ext import commands
from discord import Option
import sys
import asyncio
from discord.ui import View, Button
from collections import Counter
from discord.ui import View, Select
import requests
from discord import ApplicationContext, Embed
from discord.interactions import Interaction
#import card_game Hello





load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

GUILD_ID = 1392251301613801653

bot = discord.Bot(intents=intents, guild_ids=[GUILD_ID])

GOOGLE_APPS_URL = os.getenv("GOOGLE_APPS_URL")
GOOGLE_APPS_TOKEN = os.getenv("GOOGLE_APPS_TOKEN")
USERS_FILE = "uzivatele.json"
CODES_FILE = "kody.json"
ARTEFAKTY_FILE = "artefakty.json"
SADY_FILE = "sady.json"
VOLBY_FILE = "volby.json"


# 🔹 Pomocné funkce pro práci s JSON
def save_volba(user_id, volba):
    try:
        with open(VOLBY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}

    data[user_id] = volba

    with open(VOLBY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_volby():
    try:
        with open(VOLBY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# 🔹 View pro výběr povolání
class VolbaView(View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id

        options = [
            discord.SelectOption(label="Alchymista", description="Můžeš tvořit užitečné nástroje nebo lektvary."),
            discord.SelectOption(label="Záškodník", description="Máš vždy volbu navíc. Možnost podvodu, vydírání, lsti, atd."),
            discord.SelectOption(label="Klerik", description="Můžeš využívat své spojení s bohy, aby tě vedli na tvé cestě."),
            discord.SelectOption(label="Válečník", description="Jsi muscle mommy, která dost vydrží."),
            discord.SelectOption(label="Berserk", description="Když se naštveš, dáváš rány jako nikdo jiný."),
        ]

        select = Select(placeholder="Vyber si možnost...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        # Načteme uložené volby
        data = load_volby()

        # Kontrola, zda už uživatel volil
        if self.user_id in data:
            embed = discord.Embed(
                title="⚠️ Už jsi volil",
                description=f"Tvou volbu už máš zaznamenanou jako: **{data[self.user_id]}**",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Uložení nové volby
        vybrana = interaction.data["values"][0]
        save_volba(self.user_id, vybrana)

        embed = discord.Embed(
            title="📌 Tvoje volba byla zaznamenána",
            description=f"Vybral sis: **{vybrana}**",
            color=discord.Color.blurple()
        )
        await interaction.response.edit_message(embed=embed, view=None)


def gs_post(payload: dict):
    """Bezpečný POST na Apps Script (neblokuje logiku při chybě)."""
    if not GOOGLE_APPS_URL:
        return
    data = dict(payload)
    data["token"] = GOOGLE_APPS_TOKEN
    try:
        requests.post(GOOGLE_APPS_URL, json=data, timeout=10)
    except Exception as e:
        print(f"[GS] POST error: {e}")

def gs_get() -> list:
    """Načte dostupné kódy ze Sheet (nepovinné – hodí se pro synchronizaci při startu)."""
    if not GOOGLE_APPS_URL:
        return []
    try:
        r = requests.get(GOOGLE_APPS_URL, params={"token": GOOGLE_APPS_TOKEN}, timeout=10)
        return r.json()
    except Exception as e:
        print(f"[GS] GET error: {e}")
        return []

def gs_delete_code(code: str):
    gs_post({"action": "delete", "code": code})

def gs_add_code(artefakt_id: str, code: str):
    gs_post({"action": "add", "artefakt_id": artefakt_id, "code": code})

def gs_bulk_add(items: list[dict]):
    # items = [{ "artefakt_id": "...", "code": "..." }, ...]
    gs_post({"action": "bulk_add", "items": items})

def sync_sheet_with_artefakty():
    """
    Synchronizuje Google Sheet s JSON souborem kódů.
    Do Sheet se nahrají pouze kódy, které nejsou použité.
    """
    kody = load_json(CODES_FILE)

    # připravíme seznam nepoužitých kódů
    items_to_add = [
        {"artefakt_id": k["artefakt_id"], "code": k["code"]}
        for k in kody
        if not k.get("pouzite", False)
    ]

    # odešleme hromadně do Google Sheet
    if items_to_add:
        gs_bulk_add(items_to_add)
    print(f"[GS] Synchronizováno {len(items_to_add)} kódů do Sheet.")


# Načítání a ukládání uživatelů
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

def load_codes():
    if not os.path.exists(CODES_FILE):
        print(f"Soubor {CODES_FILE} neexistuje, vracím prázdný slovník")
        return {}
    with open(CODES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        print(f"Nahráno {len(data)} kódů ze souboru.")
        return data

def add_codes(new_codes: list[str], autor_id: str):
    codes = load_codes()
    print(f"Před přidáním: {codes}")
    for kod in new_codes:
        print(f"Přidávám kód: {kod}")
        codes[kod] = {
            "pouzity": False,
            "vytvoril": autor_id
        }
    print(f"Po přidání: {codes}")
    save_codes(codes)

# Funkce pro uložení kódů do JSON souboru
def save_codes(codes):
    print(f"Ukládám kódy do: {os.path.abspath(CODES_FILE)}")  # debug
    try:
        with open(CODES_FILE, "w", encoding="utf-8") as f:
            json.dump(codes, f, ensure_ascii=False, indent=4)
        print("✅ Soubor úspěšně uložen.")
    except Exception as e:
        print(f"❌ Chyba při ukládání kódů: {e}")


def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def update_level(user):
    xp = user.get("xp", 0)
    level = 1
    while xp >= level * 100:
        level += 1
    user["level"] = level

#kod pro vybrání frakce po registraci
def load_questions(path="otazky.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            questions = json.load(f)
    except Exception as e:
        print(f"❌ Chyba při načítání JSON souboru: {e}")
        sys.exit(1)

    errors_found = False
    for key, data in questions.items():
        if "question" not in data and not data.get("end", False):
            print(f"⚠️ Otázka '{key}' nemá text otázky.")
            errors_found = True

        if not data.get("end", False):
            if "options" not in data:
                print(f"⚠️ Otázka '{key}' nemá definované 'options'.")
                errors_found = True
                continue

            for option in data["options"]:
                if "label" not in option or "faction" not in option or "next" not in option:
                    print(f"⚠️ Chybná volba v otázce '{key}': {option}")
                    errors_found = True
                elif option["next"] not in questions:
                    print(f"❌ Neexistující 'next' cíl '{option['next']}' v otázce '{key}'")
                    errors_found = True

    if errors_found:
        print("❌ V souboru 'questions.json' byly nalezeny chyby. Oprav je před spuštěním.")
        sys.exit(1)

    print(f"✅ Načteno {len(questions)} otázek bez chyb.")
    return questions

QUESTIONS = load_questions()

async def safe_send(interaction: discord.Interaction, content=None, embed=None, view=None, **kwargs):
    """Bezpečně pošle zprávu - pokud už byla odpověď odeslána, použije followup."""
    kwargs.setdefault("ephemeral", True)
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(content=content, embed=embed, view=view, **kwargs)
        else:
            await interaction.followup.send(content=content, embed=embed, view=view, **kwargs)
    except Exception as e:
        print(f"❌ Chyba při safe_send: {e}")

class FinalChoice(discord.ui.View):
    def __init__(self, ctx, users, user_id, recommended):
        super().__init__(timeout=900)  # 15 minut
        self.ctx = ctx
        self.users = users
        self.user_id = user_id
        self.recommended = recommended
        self.other = "Přijímající" if recommended == "Očistec" else "Očistec"
        self.message = None  # uložíme později

    @discord.ui.button(label="Zvolit doporučenou frakci", style=discord.ButtonStyle.success)
    async def choose_recommended(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.assign_faction(interaction, self.recommended)

    @discord.ui.button(label="Zvolit druhou frakci", style=discord.ButtonStyle.secondary)
    async def choose_other(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.assign_faction(interaction, self.other)

    async def assign_faction(self, interaction, faction_name):
        current_faction = self.users.get(self.user_id, {}).get("frakce")
        if current_faction not in [None, "", "none", "None"]:
            await interaction.response.send_message(
                f"Už patříš do frakce **{current_faction}**. Změnu může provést pouze GM.",
                ephemeral=True
            )
            self.stop()
            return

        guild = self.ctx.guild
        role = discord.utils.get(guild.roles, name=faction_name)
        if not role:
            role = await guild.create_role(name=faction_name)

        member = guild.get_member(int(self.user_id))
        if member is None:
            await interaction.response.send_message(
                "Člen nebyl nalezen na serveru. Ujisti se, že jsi na serveru a bot má správná oprávnění.",
                ephemeral=True
            )
            return

        await member.add_roles(role)

        self.users[self.user_id]["frakce"] = faction_name
        self.users[self.user_id].pop("faction_path", None)
        save_users(self.users)

        await interaction.response.send_message(
            f"Přidal ses k **{faction_name}**.",
            ephemeral=True
        )
        self.stop()

    async def on_timeout(self):
        try:
            await self.message.edit(
                content="⏳ Čas na odpověď vypršel. Spusť příkaz `/frakce` znovu.",
                view=None
            )
        except Exception as e:
            print(f"⚠️ Nepodařilo se poslat zprávu o vypršení času (FinalChoice): {e}")


class AnswerButton(discord.ui.Button):
    def __init__(self, label, faction, next_id, parent):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.faction = faction
        self.next_id = next_id
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        user_id = self.parent.user_id
        # Přidání frakce k cestě uživatele
        self.parent.users[user_id]["faction_path"].append(self.faction)
        save_users(self.parent.users)

        if self.next_id not in QUESTIONS:
            await safe_send(interaction, "❌ Došlo k chybě: neplatný krok.")
            return

        next_data = QUESTIONS[self.next_id]

        if next_data.get("end", False):
            # Doporučená frakce podle odpovědí
            recommended = Counter(
                self.parent.users[user_id].get("faction_path", [])
            ).most_common(1)[0][0]
            view = FinalChoice(self.parent.ctx, self.parent.users, user_id, recommended)

            await interaction.response.send_message(
                f"{next_data['question']}\n\n"
                f"Na základě tvých odpovědí jsi se stal členem **{recommended}**.\n"
                f"Chceš se jím opravdu stát, nebo zvolíš druhou cestu?",
                view=view,
                ephemeral=True
            )

            # uložíme zprávu pro možnost úpravy po vypršení času
            view.message = await interaction.original_response()

        else:
            # pokračování dotazníku
            view = QuestionView(user_id, self.next_id, self.parent.users, self.parent.ctx)
            await safe_send(interaction, next_data["question"], view=view)
            view.message = await interaction.original_response()


class QuestionView(discord.ui.View):
    def __init__(self, user_id, question_id, users, ctx):
        super().__init__(timeout=900)  # 900 sekund = 15 minut
        self.user_id = user_id
        self.question_id = question_id
        self.users = users
        self.ctx = ctx
        self.message = None  # uloží se až při poslání zprávy

        question_data = QUESTIONS[question_id]
        for answer in question_data["options"]:
            self.add_item(
                AnswerButton(
                    label=answer["label"],
                    faction=answer["faction"],
                    next_id=answer["next"],
                    parent=self
                )
            )

    async def on_timeout(self):
        # po vypršení 15 minut upravíme zprávu
        if self.message:
            try:
                await self.message.edit(
                    content="⏳ Čas pro odpověď vypršel. Napiš prosím znovu `/frakce`.",
                    view=None
                )
            except discord.NotFound:
                pass  # zpráva už byla smazána nebo neexistuje

def sync_sheet_with_artefakty():
    artefakty = load_json(ARTEFAKTY_FILE)
    sheet_items = gs_get()  # [{'artefakt_id': 'artefakt_id_1', 'code': 'FN03'}, ...]
    sheet_codes = {it.get('code') for it in sheet_items}

    to_add = []
    for artefakt_id, a in artefakty.items():
        for code in a.get("kody", []):
            if code not in sheet_codes:
                to_add.append({"artefakt_id": artefakt_id, "code": code})

    if to_add:
        print(f"[GS] Doplním do Sheet {len(to_add)} kódů.")
        gs_bulk_add(to_add)


#Zapnutí bota
@bot.event
async def on_ready():
    print(f"✅ Bot online jako {bot.user} (ID {bot.user.id})")
    await bot.sync_commands()
    print("🔄 Slash příkazy synchronizovány!")

    # Jednorázová synchronizace dostupných kódů do Google Sheet
    try:
        sync_sheet_with_artefakty()
        print("🔄 Kódy úspěšně synchronizovány s Google Sheet.")
    except Exception as e:
        print(f"[GS] Chyba při synchronizaci: {e}")

# GENERUJ KÓD (pouze pro GM)
GM_IDS = [797863364629757964, 752961941370175682, 804480783464792115]

@bot.slash_command(name="generuj_kod", description="Vygeneruje jednorázový registrační kód (pouze GM).")
async def generuj_kod(ctx: discord.ApplicationContext):
    if ctx.author.id not in GM_IDS:
        await ctx.respond("Tento příkaz může použít pouze GM.", ephemeral=True)
        return

    try:
        kody = load_codes()
        kod = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        while kod in kody:
            kod = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        kody[kod] = {
            "pouzity": False,
            "vytvoril": str(ctx.author.id)
        }
        save_codes(kody)
 
        await ctx.respond(f"🔐 Registrační kód: `{kod}`\nPoužij ho příkazem `/register`.", ephemeral=True)
    except Exception as e:
        print(f"Chyba při generování kódu: {e}")
        await ctx.respond("❌ Nastala chyba při generování kódu.", ephemeral=True)


# REGISTRACE
@bot.slash_command(name="register", description="Zaregistruj se do hry s registračním kódem.")
async def register(ctx: discord.ApplicationContext, kod: discord.Option(str, description="Zadej registrační kód")):
    users = load_users()
    user_id = str(ctx.author.id)

    if user_id in users:
        await ctx.respond("Už jsi zaregistrován!", ephemeral=True)
        return

    kody = load_codes()

    if kod not in kody or kody[kod]["pouzity"]:
        await ctx.respond("❌ Neplatný nebo použitý kód.", ephemeral=True)
        return

    # Označ kód jako použitý
    kody[kod]["pouzity"] = True
    save_codes(kody)

    users[user_id] = {
        "jmeno": ctx.author.name,
        "xp": 0,
        "level": 1,
        "frakce": None
    }
    save_users(users)

    await ctx.respond(f"✅ {ctx.author.name}, byl jsi úspěšně zaregistrován! Nyní si můžeš zvolit frakci.", ephemeral=True)

@bot.slash_command(name="profile", description="Zobraz svůj nebo jiného hráče profil")
async def profile(
    ctx: discord.ApplicationContext,
    uzivatel: Option(discord.Member, "Uživatel, jehož profil chceš zobrazit", required=False) = None
):
    users = load_users()
    artefakty = load_json(ARTEFAKTY_FILE)
    sady = load_json(SADY_FILE)

    if uzivatel is None:
        uzivatel = ctx.author

    user_id = str(uzivatel.id)

    if user_id not in users:
        await ctx.respond(f"❌ Uživatel {uzivatel.display_name} není zaregistrován.", ephemeral=True)
        return

    profil = users[user_id]
    user_artefakty = profil.get("artefakty", [])

    embed = discord.Embed(title=f"🧙 Profil hráče {uzivatel.display_name}", color=discord.Color.teal())
    embed.add_field(name="Level", value=profil.get("level", 1))
    embed.add_field(name="XP", value=profil.get("xp", 0))

    current_xp = profil.get("xp", 0)
    level = profil.get("level", 1)
    xp_to_next = level * 100 - current_xp
    embed.add_field(name="XP do dalšího levelu", value=f"{xp_to_next}", inline=False)

    embed.add_field(name="Frakce", value=profil.get("frakce") or "Žádná", inline=False)

    if user_artefakty:
        seznam = ""
        for a_id in user_artefakty:
            artefakt = artefakty.get(a_id)
            if artefakt:
                nazev = artefakt.get("nazev", a_id)
                sada = artefakt.get("sada", "❓")
                seznam += f"• {nazev} *({sada})*\n"
        embed.add_field(name="💎 Artefakty", value=seznam, inline=False)
    else:
        embed.add_field(name="💎 Artefakty", value="Nemá žádné artefakty.", inline=False)

    dokoncene_sady = ""
    zapocate_sady = ""

    for sada_id, sada in sady.items():
        artefakty_v_sade = sada.get("artefakty", [])
        nazev = sada.get("nazev", sada_id)
        splnenych = sum(1 for a in artefakty_v_sade if a in user_artefakty)
        celkem = len(artefakty_v_sade)

        if splnenych == celkem and celkem > 0:
            dokoncene_sady += f"• {nazev} ✅ ({splnenych}/{celkem})\n"
        elif splnenych > 0:
            zapocate_sady += f"• {nazev}: {splnenych}/{celkem}\n"

    if dokoncene_sady:
        embed.add_field(name="🏆 Dokončené sady", value=dokoncene_sady, inline=False)
    if zapocate_sady:
        embed.add_field(name="🧩 Započaté sady", value=zapocate_sady, inline=False)

    await ctx.respond(embed=embed, ephemeral=True)

#  UNREGISTER
@bot.slash_command(name="unregister", description="Smaž svůj účet")
async def unregister(ctx: discord.ApplicationContext):
    users = load_users()
    user_id = str(ctx.author.id)

    if user_id in users:
        del users[user_id]
        save_users(users)
        await ctx.respond("Tvoje data byla smazána.", ephemeral=True)
    else:
        await ctx.respond("Nemáš vytvořený účet.", ephemeral=True)

# FRAKCE
@bot.slash_command(name="frakce", description="Začni cestu k výběru frakce.")
async def frakce(ctx: discord.ApplicationContext):
    await ctx.defer(ephemeral=True)

    users = load_users()
    user_id = str(ctx.author.id)

    if user_id not in users:
        await ctx.followup.send("Nejprve se zaregistruj pomocí /register.", ephemeral=True)
        return

    users[user_id]["faction_path"] = []
    save_users(users)

    view = QuestionView(user_id, "start", users, ctx)
    msg = await ctx.followup.send(content=QUESTIONS["start"]["question"], view=view, ephemeral=True)
    view.message = msg


#Artefakty
# Slovník pro převod rarity na barvu a emoji
RARITY_SETTINGS = {
    "obyčejná": {"color": discord.Color.light_grey(), "emoji": "⚪"},
    "neobyčejná": {"color": discord.Color.green(), "emoji": "🟢"},
    "vzácná": {"color": discord.Color.blue(), "emoji": "🔵"},
    "epická": {"color": discord.Color.purple(), "emoji": "🟣"},
    "legendární": {"color": discord.Color.gold(), "emoji": "🟡"},
    "mytická": {"color": discord.Color.red(), "emoji": "🔴"},
}

# --- Vytvoření Embed pro artefakty ---
def vytvor_embed(artefakt: dict, zprava_uvod: str = None, sady: dict = None,
                 uzivatel_artefakty: list = None, uzivatel_level: int = 1) -> discord.Embed:
    rarity = artefakt.get("rarita", "obyčejná").lower()
    settings = RARITY_SETTINGS.get(rarity, RARITY_SETTINGS["obyčejná"])
    popis = artefakt.get("popis", "Žádný popis.")
    if zprava_uvod:
        popis = f"{zprava_uvod}\n\n{popis}"

    embed = discord.Embed(
        title=f"{settings['emoji']} {artefakt['nazev']}",
        description=popis,
        color=settings["color"]
    )

    if "typ" in artefakt:
        embed.add_field(name="Typ", value=artefakt["typ"], inline=True)
    if "rarita" in artefakt:
        embed.add_field(name="Rarita", value=rarity.capitalize(), inline=True)
    if "bonusy" in artefakt:
        bonusy_text = "\n".join([f"• {k}: {v}" for k, v in artefakt["bonusy"].items()])
        embed.add_field(name="Bonusy", value=bonusy_text, inline=False)

    if sady and uzivatel_artefakty is not None:
        sada_id = artefakt.get("sada")
        if sada_id and sada_id in sady:
            sada = sady[sada_id]
            vsechny = sada.get("artefakty", [])
            ziskane = [a for a in vsechny if a in uzivatel_artefakty]
            pokrok_text = f"{len(ziskane)}/{len(vsechny)} artefaktů"
            podminky = sada.get("podminky", {})
            splneno = uzivatel_level >= podminky.get("level", 0)
            if len(ziskane) == len(vsechny) and splneno:
                pokrok_text += "\n🏆 Dokončil jsi sadu!"
            elif not splneno:
                pokrok_text += "\n🔒 Ještě nesplňuješ podmínky pro dokončení sady."
            embed.add_field(name=f"Pokrok v sadě {sada['nazev']}", value=pokrok_text, inline=False)
    return embed

# --- Slash command artefakt ---
@bot.slash_command(name="artefakt", description="Získání nebo zobrazení artefaktu.")
async def artefakt(
    ctx: discord.ApplicationContext,
    kod: discord.Option(str, description="Zadej kód pro získání artefaktu", required=False),
    jmeno: discord.Option(str, description="Zadej název artefaktu pro zobrazení", required=False)
):
    # Odložíme odpověď, protože může chvíli trvat zpracování
    await ctx.defer(ephemeral=True)

    user_id = str(ctx.author.id)
    users = load_users()
    artefakty = load_json(ARTEFAKTY_FILE)  # tady jsou i kódy
    sady = load_json(SADY_FILE)

    if kod:
        if user_id not in users:
            await ctx.followup.send("❌ Nejsi zaregistrován. Použij příkaz `/register`.", ephemeral=True)
            return

        kod = kod.strip().upper()
        artefakt_id = None
        artefakt_data = None

        # Najdeme artefakt podle kódu v artefakty.json
        for aid, data in artefakty.items():
            kody_normalized = [k.strip().upper() for k in data.get("kody", [])]
            pouzite_normalized = [k.strip().upper() for k in data.get("pouzite_kody", [])]

            if kod in kody_normalized:
                artefakt_id = aid
                artefakt_data = data
                # přesuneme kód z "kody" do "pouzite_kody"
                data["kody"].remove(next(k for k in data["kody"] if k.strip().upper() == kod))
                data.setdefault("pouzite_kody", []).append(kod)
                break

            if kod in pouzite_normalized:
                await ctx.followup.send("❌ Tento kód už byl použit.", ephemeral=True)
                return

        if artefakt_id is None:
            await ctx.followup.send("❌ Neplatný kód.", ephemeral=True)
            return

        # Uživatel
        user = users[user_id]
        user.setdefault("artefakty", [])
        user.setdefault("pouzite_kody", [])
        user.setdefault("level", 1)

        # Přidáme artefakt hráči
        user["artefakty"].append(artefakt_id)
        user["pouzite_kody"].append(kod)

        # Uložíme JSONy
        save_users(users)
        save_json(artefakty, ARTEFAKTY_FILE)

        # Odebereme kód ze Sheet (dostupné kódy)
        try:
            gs_delete_code(kod)
        except Exception as e:
            print(f"[GS] Nepodařilo se odstranit kód ze Sheet: {e}")

        # Embed pro artefakt
        uvodni_zprava = f"✅ Získal jsi artefakt **{artefakt_data['nazev']}**"
        embed = vytvor_embed(
            artefakt=artefakt_data,
            zprava_uvod=uvodni_zprava,
            sady=sady,
            uzivatel_artefakty=user["artefakty"],
            uzivatel_level=user.get("level", 1)
        )
        await ctx.followup.send(embed=embed, ephemeral=True)
        return

    elif jmeno:
        # Zobrazení artefaktu podle jména
        jmeno_lower = jmeno.lower()
        shody = [a for a in artefakty.values() if jmeno_lower in a.get("nazev", "").lower()]

        if len(shody) == 0:
            await ctx.followup.send(f"❌ Artefakt obsahující v názvu **{jmeno}** nebyl nalezen.", ephemeral=True)
            return
        elif len(shody) == 1:
            artefakt_data = shody[0]
            uzivatel_artefakty = users.get(user_id, {}).get("artefakty", [])
            uzivatel_level = users.get(user_id, {}).get("level", 1)
            embed = vytvor_embed(
                artefakt=artefakt_data,
                sady=sady,
                uzivatel_artefakty=uzivatel_artefakty,
                uzivatel_level=uzivatel_level
            )
            await ctx.followup.send(embed=embed, ephemeral=True)
            return
        else:
            view = ArtefaktSelect(shody, users, user_id, sady, ctx)
            message = await ctx.followup.send(
                f"🔍 Našel jsem více artefaktů odpovídajících výrazu **{jmeno}**. Vyber si jeden:",
                view=view,
                ephemeral=True
            )
            view.message = message


class ArtefaktSelect(discord.ui.View):
    def __init__(self, shody, users, user_id, sady, ctx):
        super().__init__(timeout=900)
        self.shody = shody
        self.users = users
        self.user_id = user_id
        self.sady = sady
        self.ctx = ctx
        self.message = None

        options = [
            discord.SelectOption(
                label=a["nazev"],
                description=a.get("rarita", "obyčejná").capitalize(),
                emoji=RARITY_SETTINGS.get(a.get("rarita", "obyčejná").lower(), RARITY_SETTINGS["obyčejná"])["emoji"]
            )
            for a in shody
        ]

        select = discord.ui.Select(
            placeholder="Vyber artefakt…",
            options=options,
            min_values=1,
            max_values=1
        )
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        vybrany_nazev = interaction.data["values"][0]
        artefakt_data = next((a for a in self.shody if a["nazev"] == vybrany_nazev), None)

        if artefakt_data:
            uzivatel_artefakty = self.users.get(self.user_id, {}).get("artefakty", [])
            uzivatel_level = self.users.get(self.user_id, {}).get("level", 1)
            embed = vytvor_embed(
                artefakt=artefakt_data,
                sady=self.sady,
                uzivatel_artefakty=uzivatel_artefakty,
                uzivatel_level=uzivatel_level
            )
            await interaction.response.edit_message(content=None, embed=embed, view=None)
        else:
            await interaction.response.send_message("❌ Artefakt nebyl nalezen.", ephemeral=True)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(
                    content="⏰ Vypršel čas pro výběr artefaktu. Použij znovu příkaz /artefakt.",
                    view=None
                )
            except discord.HTTPException:
                pass


# Sady
@bot.slash_command(name="sady", description="Prohlížení všech sad artefaktů")
async def sady(ctx: discord.ApplicationContext):
    users = load_users()
    artefakty = load_json(ARTEFAKTY_FILE)
    sady_data = load_json(SADY_FILE)
    sady_list = list(sady_data.items())

    if not sady_list:
        await ctx.respond("Žádné sady nejsou k dispozici.", ephemeral=True)
        return

    view = SadyView(ctx, sady_list, artefakty)
    embed = view.vytvor_embed()
    msg = await ctx.respond(embed=embed, view=view, ephemeral=True)
    view.message = await ctx.interaction.original_response()  


class SadyView(discord.ui.View):
    def __init__(self, ctx, sady_list, artefakty):
        super().__init__(timeout=900)  # 15 minut
        self.ctx = ctx
        self.sady_list = sady_list
        self.artefakty = artefakty
        self.index = 0
        self.message = None  # nastavíme po odeslání

    def vytvor_embed(self):
        sada_id, sada = self.sady_list[self.index]
        nazev_sady = sada.get("nazev", sada_id)
        popis_sady = sada.get("popis", "Bez popisu.")

        embed = discord.Embed(
            title=f"📖 Sada {nazev_sady}",
            description=popis_sady,
            color=discord.Color.dark_red()
        )

        artefakty_ids = sada.get("artefakty", [])
        artefakty_text = ""
        for aid in artefakty_ids:
            artefakt = self.artefakty.get(aid, {})
            artefakty_text += f"• **{artefakt.get('nazev', aid)}**\n"

        podminky = sada.get("podminky", {})
        podminky_text = f"- Level {podminky.get('level', 0)}"

        embed.add_field(name="🔹 Artefakty", value=artefakty_text or "Žádné", inline=False)
        embed.add_field(name="🧾 Podmínky", value=podminky_text or "Žádné", inline=False)
        embed.set_footer(text=f"Sada {self.index + 1} z {len(self.sady_list)}")
        return embed

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def back(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Tohle není tvoje kniha!", ephemeral=True)
            return
        self.index = (self.index - 1) % len(self.sady_list)
        await interaction.response.edit_message(embed=self.vytvor_embed(), view=self)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def forward(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Tohle není tvoje kniha!", ephemeral=True)
            return
        self.index = (self.index + 1) % len(self.sady_list)
        await interaction.response.edit_message(embed=self.vytvor_embed(), view=self)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(
                    content="⏰ Vypršel čas pro procházení sad. Použij znovu příkaz /sady.",
                    view=None
                )
            except Exception:
                pass


    
#Daily odměna
@bot.slash_command(name="daily", description="Získej denní odměnu XP.")
async def daily(ctx: discord.ApplicationContext):
    users = load_users()
    user_id = str(ctx.author.id)

    if user_id not in users:
        await ctx.respond("Nejsi zaregistrován. Použij `/register`.", ephemeral=True)
        return

    user = users[user_id]
    last_daily = user.get("last_daily", 0)
    current_time = int(time.time())

    if current_time - last_daily < 24 * 3600:
        remaining = 24 * 3600 - (current_time - last_daily)
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await ctx.respond(f"⏳ Už jsi dnes získal denní odměnu. Zkus to znovu za {hours}h {minutes}m.", ephemeral=True)
        return


    # Přidání XP za daily
    gained_xp = 50
    user["xp"] = user.get("xp", 0) + gained_xp

    # Aktualizace levelu podle XP
    update_level(user)

    # Uložení času posledního použití
    user["last_daily"] = current_time

    save_users(users)

    # Spočítat XP do dalšího levelu
    current_xp = user["xp"]
    current_level = user["level"]
    xp_next_level = current_level * 100
    xp_to_next = xp_next_level - current_xp

    await ctx.respond(
        f"🎉 Získal jsi {gained_xp} XP! Nyní máš level {current_level}.\n"
        f"Do dalšího levelu ti chybí {xp_to_next} XP.",
        ephemeral=True
    )


@bot.slash_command(name="volba", description="Vyber povolání Eliry.")
async def volba(ctx):
    embed = discord.Embed(title="Volba povolání", color=discord.Color.dark_red())

    embed.add_field(name="Úvod", value=(
        "Temnota se vkrádá do každé skuliny. Morbus Tenebrae – mor stínů – se šíří zemí jako jed, co nemá lék. "
        "Vesnice umlkají, cesty zejí prázdnotou a na troskách se rodí nové kulty i zoufalí hrdinové."
    ), inline=False)

    embed.add_field(name="Příběh Eliry", value=(
        "Mezi těmi, kdo přežili, stojí mladá dívka jménem Elira. Není hrdinkou z písní ani dcerou mocných rodů. "
        "Je to obyčejná lidská holka, jejíž dětství ukradl stín. Viděla mizet své přátele, slyšela šeptání temnoty ve snech "
        "a příliš brzy pochopila, že ve světě, kde vládne nemoc, musíš buď bojovat – nebo se stát kořistí."
    ), inline=False)

    embed.add_field(name="Osud v tvých rukou", value=(
        "Elira není vyvolená. Není předurčená. Je jen jedna z mnoha. Ale právě proto má šanci změnit svět – protože odmítla čekat na smrt. "
        "Protože se rozhodla vzít svůj osud do vlastních rukou.\n\n"
        "A teď i ty držíš její příběh. Je na tobě, kým se Elira stane. Cesta ji povede temnotou, krví i ohněm. "
        "Ale jakou zbraní se obrní, to je tvá volba."
    ), inline=False)

    # Zobraz Select menu pro volbu povolání
    await ctx.respond(embed=embed, view=VolbaView(str(ctx.author.id)), ephemeral=True)

bot.run(TOKEN)

   
