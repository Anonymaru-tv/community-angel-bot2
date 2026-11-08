# ==========================================
# DISCORD COMMUNITY & RPG ANGEL-BOT (bot.py)
# ==========================================
import os
import random
import time
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands
from config import (
    BUSINESS_TYPES,
    MYSTIC_CARDS,
    NPC_FIRST_NAMES,
    NPC_LAST_NAMES,
    PROMI_CARDS,
    BAIT_TIERS
)

DB_NAME = os.environ.get("DB_PATH", "community_fishing.db")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================================
# 1. SPIELDATEN & KONFIGURATION
# ==========================================
BASE_FISH_LOOT = [
    ("Alter Stiefel", "Müll", 5, 20),
    ("Plastikflasche", "Müll", 3, 18),
    ("Rotauge", "Gewöhnlich", 25, 22),
    ("Flussbarsch", "Gewöhnlich", 45, 14),
    ("Regenbogenforelle", "Selten", 110, 8),
    ("Hecht", "Selten", 180, 5),
    ("Atlantischer Lachs", "Episch", 450, 1.8),
    ("Geister-Stör", "Legendär", 1500, 0.4),
]

ALL_FISH_LOOT = list(BASE_FISH_LOOT)
for mf in MYSTIC_CARDS.keys():
    ALL_FISH_LOOT.append((f"🔮 {mf}", "Mystisch", 3500, 0.08))

for pf in PROMI_CARDS.keys():
    ALL_FISH_LOOT.append((f"🌟 {pf}", "Ultraselten", 6500, 0.04))

RODS = {
    1: {"name": "Bambusrute", "cost": 0, "luck_mult": 1.0},
    2: {"name": "Fiberglasrute", "cost": 300, "luck_mult": 1.3},
    3: {"name": "Karbon-Meisterrute", "cost": 1200, "luck_mult": 1.8},
    4: {"name": "Neptuns Dreizack", "cost": 5000, "luck_mult": 2.5},
}

# ==========================================
# 7 IMMERSIVE VERZAUBERUNGEN
# ==========================================
ENCHANTMENTS = {
    "luck": {
        "name": "Glück des Meeres",
        "emoji": "✨",
        "db_col": "ench_luck",
        "levels": {
            1: {"cost": 250, "bonus": 1.25, "desc": "+25% Seltenheits-Chance"},
            2: {"cost": 750, "bonus": 1.60, "desc": "+60% Seltenheits-Chance"},
            3: {"cost": 2000, "bonus": 2.20, "desc": "+120% Seltenheits-Chance"}
        }
    },
    "lure_save": {
        "name": "Köder-Sparer",
        "emoji": "🪱",
        "db_col": "ench_lure_save",
        "levels": {
            1: {"cost": 300, "chance": 0.30, "desc": "30% Chance, Köder zu behalten"},
            2: {"cost": 900, "chance": 0.60, "desc": "60% Chance, Köder zu behalten"}
        }
    },
    "treasure": {
        "name": "Schatzsucher",
        "emoji": "🏴‍☠️",
        "db_col": "ench_treasure",
        "levels": {
            1: {"cost": 1500, "chance": 0.15, "desc": "15% Chance auf Münztruhen (150-450 🪙)"}
        }
    },
    "giant": {
        "name": "Giganten-Köder",
        "emoji": "⚖️",
        "db_col": "ench_giant",
        "levels": {
            1: {"cost": 600, "mult": 1.25, "desc": "+25% Fischgewicht & Wert"},
            2: {"cost": 1800, "mult": 1.60, "desc": "+60% Fischgewicht & Wert"},
            3: {"cost": 4500, "mult": 2.00, "desc": "+100% Fischgewicht & doppelter Wert!"}
        }
    },
    "double": {
        "name": "Doppel-Haken",
        "emoji": "🪞",
        "db_col": "ench_double",
        "levels": {
            1: {"cost": 1200, "chance": 0.20, "desc": "20% Chance, 2 Fische gleichzeitig zu ziehen"},
            2: {"cost": 3500, "chance": 0.40, "desc": "40% Chance, 2 Fische gleichzeitig zu ziehen"}
        }
    },
    "purity": {
        "name": "Neptuns Segen",
        "emoji": "🌊",
        "db_col": "ench_purity",
        "levels": {
            1: {"cost": 2200, "desc": "Verbannt jeglichen Müll (Stiefel/Plastik) von deinem Haken!"}
        }
    },
    "haste": {
        "name": "Blitz-Reflexe",
        "emoji": "⚡",
        "db_col": "ench_haste",
        "levels": {
            1: {"cost": 1000, "cooldown": 6.0, "desc": "Verkürzt den Angel-Cooldown auf 6 Sekunden"},
            2: {"cost": 3000, "cooldown": 3.0, "desc": "Verkürzt den Angel-Cooldown auf 3 Sekunden!"}
        }
    }
}

COMMUNITY_SHOP_ITEMS = {
    "ring": {"name": "💍 Ehering", "cost": 2500, "desc": "Wird benötigt, um einem anderen Mitglied einen Heiratsantrag zu machen!"},
    "hut": {"name": "⛺ Strandhütte", "cost": 5000, "desc": "Ein gemütliches Holzhäuschen an der Küste."},
    "villa": {"name": "🏰 Luxus-Villa", "cost": 25000, "desc": "Ein riesiges Anwesen für deine Familie."},
    "gull": {"name": "🕊️ Zahme Möwe", "cost": 1200, "desc": "Ein treuer Begleiter beim Fischen."},
    "title_king": {"name": "👑 Fischerkönig-Titel", "cost": 50000, "desc": "Das ultimative Statussymbol für dein Profil."}
}

# Dynamischer Speicher für Cooldowns basierend auf Blitz-Reflexe
USER_LAST_FISHED = {}

# ==========================================
# 2. DATENBANK-SCHICHT & AUTO-MIGRATION
# ==========================================
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                welcome_channel_id INTEGER,
                autorole_id INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id INTEGER PRIMARY KEY,
                coins INTEGER DEFAULT 100,
                rod_level INTEGER DEFAULT 1,
                baits INTEGER DEFAULT 5,
                bait_tier INTEGER DEFAULT 1,
                bucket_flipped INTEGER DEFAULT 0,
                ench_luck INTEGER DEFAULT 0,
                ench_lure_save INTEGER DEFAULT 0,
                ench_treasure INTEGER DEFAULT 0,
                ench_giant INTEGER DEFAULT 0,
                ench_double INTEGER DEFAULT 0,
                ench_purity INTEGER DEFAULT 0,
                ench_haste INTEGER DEFAULT 0,
                spouse_id INTEGER DEFAULT NULL,
                parent_id INTEGER DEFAULT NULL
            )
        """)
        for col_def in [
            ("bait_tier", "INTEGER DEFAULT 1"),
            ("bucket_flipped", "INTEGER DEFAULT 0"),
            ("ench_giant", "INTEGER DEFAULT 0"),
            ("ench_double", "INTEGER DEFAULT 0"),
            ("ench_purity", "INTEGER DEFAULT 0"),
            ("ench_haste", "INTEGER DEFAULT 0"),
            ("spouse_id", "INTEGER DEFAULT NULL"),
            ("parent_id", "INTEGER DEFAULT NULL")
        ]:
            try:
                await db.execute(f"ALTER TABLE user_profiles ADD COLUMN {col_def[0]} {col_def[1]}")
            except Exception:
                pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                fish_name TEXT,
                fish_rarity TEXT,
                fish_weight REAL,
                value INTEGER,
                original_catcher_id INTEGER DEFAULT NULL
            )
        """)
        try:
            await db.execute("ALTER TABLE user_inventory ADD COLUMN original_catcher_id INTEGER DEFAULT NULL")
        except Exception:
            pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_rpg_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_key TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS businesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                business_type TEXT,
                custom_name TEXT,
                vault_coins INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS business_shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER,
                user_id INTEGER,
                shares_owned INTEGER DEFAULT 0,
                UNIQUE(business_id, user_id)
            )
        """)
        await db.commit()

async def get_profile(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT coins, rod_level, baits, bait_tier, bucket_flipped,
                   ench_luck, ench_lure_save, ench_treasure, ench_giant,
                   ench_double, ench_purity, ench_haste,
                   spouse_id, parent_id
            FROM user_profiles WHERE user_id = ?
        """, (user_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                await db.execute("INSERT INTO user_profiles (user_id) VALUES (?)", (user_id,))
                await db.commit()
                return {
                    "coins": 100, "rod_level": 1, "baits": 5, "bait_tier": 1,
                    "bucket_flipped": 0, "ench_luck": 0, "ench_lure_save": 0,
                    "ench_treasure": 0, "ench_giant": 0, "ench_double": 0,
                    "ench_purity": 0, "ench_haste": 0,
                    "spouse_id": None, "parent_id": None
                }
            return {
                "coins": row[0], "rod_level": row[1], "baits": row[2], "bait_tier": row[3],
                "bucket_flipped": row[4], "ench_luck": row[5], "ench_lure_save": row[6],
                "ench_treasure": row[7], "ench_giant": row[8], "ench_double": row[9],
                "ench_purity": row[10], "ench_haste": row[11],
                "spouse_id": row[12], "parent_id": row[13]
            }

# ==========================================
# 3. FAMILIEN-FINANZSYSTEM (25% EHE & 5% TASCHENGELD)
# ==========================================
async def distribute_family_income(db: aiosqlite.Connection, user_id: int, gross_amount: int) -> dict:
    if gross_amount <= 0:
        return {"net": 0, "spouse_cut": 0, "children_cut": 0, "spouse_id": None, "children_count": 0}

    async with db.execute("SELECT spouse_id FROM user_profiles WHERE user_id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
        spouse_id = row[0] if row else None

    async with db.execute("SELECT user_id FROM user_profiles WHERE parent_id = ?", (user_id,)) as cur:
        children_rows = await cur.fetchall()
        children_ids = [r[0] for r in children_rows]

    spouse_cut = 0
    if spouse_id:
        spouse_cut = int(gross_amount * 0.25)
        if spouse_cut > 0:
            await db.execute("UPDATE user_profiles SET coins = coins + ? WHERE user_id = ?", (spouse_cut, spouse_id))

    children_cut = 0
    if children_ids:
        children_cut = int(gross_amount * 0.05)
        if children_cut > 0:
            cut_per_child = children_cut // len(children_ids)
            rem = children_cut % len(children_ids)
            for idx, cid in enumerate(children_ids):
                add_coins = cut_per_child + (1 if idx == 0 else 0)
                await db.execute("UPDATE user_profiles SET coins = coins + ? WHERE user_id = ?", (add_coins, cid))

    net_amount = gross_amount - spouse_cut - children_cut
    await db.execute("UPDATE user_profiles SET coins = coins + ? WHERE user_id = ?", (net_amount, user_id))

    return {
        "net": net_amount,
        "spouse_cut": spouse_cut,
        "children_cut": children_cut,
        "spouse_id": spouse_id,
        "children_count": len(children_ids)
    }

def format_family_note(tax_info: dict) -> str:
    notes = []
    if tax_info["spouse_cut"] > 0:
        notes.append(f"💍 **{tax_info['spouse_cut']:,} 🪙 (25%)** an Ehepartner <@{tax_info['spouse_id']}> überwiesen.".replace(",", "."))
    if tax_info["children_cut"] > 0:
        notes.append(f"🧸 **{tax_info['children_cut']:,} 🪙 (5%)** Taschengeld an {tax_info['children_count']} Kind(er) verteilt.".replace(",", "."))
    if notes:
        return "\n" + "\n".join(notes)
    return ""

# ==========================================
# 4. BOT EVENTS & COMMUNITY SETTINGS
# ==========================================
@bot.event
async def on_ready():
    await init_db()
    await bot.tree.sync()
    print(f"Bot erfolgreich gestartet als {bot.user} (ID: {bot.user.id})")

@bot.event
async def on_member_join(member: discord.Member):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT welcome_channel_id, autorole_id FROM guild_settings WHERE guild_id = ?", (member.guild.id,)) as cur:
            row = await cur.fetchone()
    if not row:
        return
    welcome_ch_id, autorole_id = row
    if autorole_id:
        role = member.guild.get_role(autorole_id)
        if role and member.guild.me.guild_permissions.manage_roles:
            await member.add_roles(role)
    if welcome_ch_id:
        ch = member.guild.get_channel(welcome_ch_id)
        if ch:
            embed = discord.Embed(
                title="Willkommen im Hafen! ⚓",
                description=f"Sei gegrüßt, {member.mention}! Schnapp dir deine Angel mit `/angel` oder besuche den `/hafenmarkt`!",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await ch.send(embed=embed)

class SettingsGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="settings", description="Verwalte Server-Einstellungen")

    @app_commands.command(name="welcome_channel", description="Kanal für Begrüßungen festlegen")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_welcome(self, interaction: discord.Interaction, channel: discord.TextChannel):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                INSERT INTO guild_settings (guild_id, welcome_channel_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET welcome_channel_id = excluded.welcome_channel_id
            """, (interaction.guild_id, channel.id))
            await db.commit()
        await interaction.response.send_message(f"✅ Willkommenskanal: {channel.mention}")

    @app_commands.command(name="autorole", description="Rolle für neue Mitglieder einstellen")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_autorole(self, interaction: discord.Interaction, role: discord.Role):
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                INSERT INTO guild_settings (guild_id, autorole_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET autorole_id = excluded.autorole_id
            """, (interaction.guild_id, role.id))
            await db.commit()
        await interaction.response.send_message(f"✅ Auto-Rolle: **@{role.name}**")

bot.tree.add_command(SettingsGroup())

# ==========================================
# 5. ANGELSYSTEM MIT ALLEN 7 VERZAUBERUNGEN
# ==========================================
def get_card_data(raw_name: str):
    clean = raw_name.replace("🔮 ", "").replace("🌟 ", "")
    if clean in PROMI_CARDS:
        return PROMI_CARDS[clean]["img"], PROMI_CARDS[clean]["title"]
    if clean in MYSTIC_CARDS:
        return MYSTIC_CARDS[clean], "Uraltes Tiefsee-Mysterium"
    return None, None

@bot.tree.command(name="angel", description="Wirf deine Rute aus!")
async def fish(interaction: discord.Interaction):
    profile = await get_profile(interaction.user.id)
    now = time.time()

    # Blitz-Reflexe Verzauberung: Cooldown dynamisch anpassen (Standard 10s, Stufe 1: 6s, Stufe 2: 3s)
    cooldown_time = 10.0
    if profile["ench_haste"] == 1:
        cooldown_time = 6.0
    elif profile["ench_haste"] >= 2:
        cooldown_time = 3.0

    last_fished = USER_LAST_FISHED.get(interaction.user.id, 0)
    time_passed = now - last_fished
    if time_passed < cooldown_time:
        rem_sec = cooldown_time - time_passed
        return await interaction.response.send_message(
            f"⏳ Deine Angelschnur ist noch feucht! Warte noch **{rem_sec:.1f}s**.",
            ephemeral=True
        )

    if profile["baits"] <= 0:
        return await interaction.response.send_message("🪱 Keine Köder mehr! Kaufe neue im `/shop`.", ephemeral=True)

    USER_LAST_FISHED[interaction.user.id] = now
    rod = RODS[profile["rod_level"]]
    current_bait = BAIT_TIERS.get(profile["bait_tier"], BAIT_TIERS[1])
    allowed = current_bait["allowed_rarities"]

    # 1. Köder-Sparer prüfen
    bait_consumed = True
    if profile["ench_lure_save"] > 0:
        save_chance = ENCHANTMENTS["lure_save"]["levels"][profile["ench_lure_save"]]["chance"]
        if random.random() < save_chance:
            bait_consumed = False

    # 2. Glück des Meeres Multiplikator
    luck_mult = rod["luck_mult"]
    if profile["ench_luck"] > 0:
        luck_mult *= ENCHANTMENTS["luck"]["levels"][profile["ench_luck"]]["bonus"]

    # 3. Schatzsucher
    found_treasure = False
    treasure_coins = 0
    treasure_tax_info = None
    if profile["ench_treasure"] == 1 and random.random() < ENCHANTMENTS["treasure"]["levels"][1]["chance"]:
        found_treasure = True
        treasure_coins = random.randint(150, 450)

    # 4. Neptuns Segen: Entfernt Müll komplett
    filtered_pool = [f for f in ALL_FISH_LOOT if f[1] in allowed]
    if profile["ench_purity"] >= 1:
        filtered_pool = [f for f in filtered_pool if f[1] != "Müll"]

    weights = []
    for _, rarity, _, base_chance in filtered_pool:
        if rarity in ["Müll", "Gewöhnlich"]:
            weights.append(max(base_chance / luck_mult, 0.3))
        else:
            weights.append(base_chance * luck_mult)

    selected_fish = random.choices(filtered_pool, weights=weights, k=1)[0]
    name, rarity, base_val, _ = selected_fish

    # 5. Giganten-Köder Multiplikator auf Gewicht & Wert
    giant_mult = 1.0
    if profile["ench_giant"] > 0:
        giant_mult = ENCHANTMENTS["giant"]["levels"][profile["ench_giant"]]["mult"]

    raw_weight = round(random.uniform(0.5, 25.0) * (2.0 if rarity in ["Episch", "Legendär", "Mystisch", "Ultraselten"] else 1.0), 2)
    final_weight = round(raw_weight * giant_mult, 2)
    final_value = int(base_val * (1 + (final_weight / 10)))

    # 6. Doppel-Haken: Chance auf zweiten identischen Fisch
    caught_count = 1
    if profile["ench_double"] > 0:
        double_chance = ENCHANTMENTS["double"]["levels"][profile["ench_double"]]["chance"]
        if random.random() < double_chance:
            caught_count = 2

    async with aiosqlite.connect(DB_NAME) as db:
        if bait_consumed:
            await db.execute("UPDATE user_profiles SET baits = baits - 1 WHERE user_id = ?", (interaction.user.id,))
        if found_treasure:
            treasure_tax_info = await distribute_family_income(db, interaction.user.id, treasure_coins)

        for _ in range(caught_count):
            await db.execute("""
                INSERT INTO user_inventory (user_id, fish_name, fish_rarity, fish_weight, value, original_catcher_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (interaction.user.id, name, rarity, final_weight, final_value, interaction.user.id))
        await db.commit()

    rarity_colors = {
        "Müll": discord.Color.light_grey(),
        "Gewöhnlich": discord.Color.blue(),
        "Selten": discord.Color.purple(),
        "Episch": discord.Color.magenta(),
        "Legendär": discord.Color.gold(),
        "Mystisch": discord.Color.from_rgb(155, 89, 182),
        "Ultraselten": discord.Color.from_rgb(230, 126, 34)
    }

    embed_title = "🎣 Ein Fang hat angebissen!" if caught_count == 1 else "🪞 DOPPEL-FANG! Zwei Fische am Haken! 🎉"
    embed = discord.Embed(
        title=embed_title,
        description=f"Eingeholt mit **{rod['name']}** & {current_bait['emoji']} **{current_bait['name']}**!",
        color=rarity_colors.get(rarity, discord.Color.blue())
    )
    fish_desc = f"**{name}**\n*Seltenheit: {rarity}*"
    if caught_count == 2:
        fish_desc += " **(x2 erhalten!)**"

    embed.add_field(name="Fang", value=fish_desc, inline=True)
    embed.add_field(name="Gewicht (je)", value=f"{final_weight} kg" + (f" *(+{int((giant_mult-1)*100)}% Gigant)*" if giant_mult > 1.0 else ""), inline=True)
    embed.add_field(name="Wert (je)", value=f"{final_value:,} 🪙".replace(",", "."), inline=True)

    img_url, subtitle = get_card_data(name)
    if img_url:
        embed.set_image(url=img_url)
        embed.add_field(name="🃏 Sammelkarte freigeschaltet!", value=f"*{subtitle}*\n*Erstfänger:* {interaction.user.mention}", inline=False)

    extra_notes = []
    if caught_count == 2:
        extra_notes.append("🪞 *Doppel-Haken aktiv: Du hast gleich ZWEI Fische auf einmal aus dem Wasser gezogen!*")
    if giant_mult > 1.0:
        extra_notes.append(f"⚖️ *Giganten-Köder aktiv: Das Gewicht wurde massiv gesteigert!*")
    if profile["ench_purity"] >= 1:
        extra_notes.append("🌊 *Neptuns Segen aktiv: Jeglicher Müll wird von deiner Schnur abgewehrt!*")
    if profile["ench_haste"] > 0:
        extra_notes.append(f"⚡ *Blitz-Reflexe aktiv: Dein Cooldown beträgt nur {cooldown_time:.0f}s!*")
    if not bait_consumed:
        extra_notes.append("✨ *Köder-Sparer aktiv: Köder behalten!*")
    if found_treasure and treasure_tax_info:
        msg = f"🏴‍☠️ *Schatzsucher! Bruttogewinn: **{treasure_coins} 🪙** (Netto: **+{treasure_tax_info['net']:,} 🪙**)*".replace(",", ".")
        fam_note = format_family_note(treasure_tax_info)
        extra_notes.append(msg + (f"\n{fam_note}" if fam_note else ""))

    if extra_notes:
        embed.add_field(name="Besondere Verzauberungseffekte", value="\n".join(extra_notes), inline=False)

    rem_baits = profile["baits"] if not bait_consumed else profile["baits"] - 1
    embed.set_footer(text=f"Köder: {rem_baits}x {current_bait['name']} | Cooldown: {cooldown_time:.0f}s | Karten: /sammelkarte")
    await interaction.response.send_message(embed=embed)

# ==========================================
# 6. COINFLIP: DER GANZE EIMER (50/50 RISK)
# ==========================================
@bot.tree.command(name="coinflip_eimer", description="Setze deinen GANZEN Eimer aufs Spiel! 50/50: Verdopple den Wert aller Fische oder verliere alles!")
async def coinflip_bucket(interaction: discord.Interaction):
    profile = await get_profile(interaction.user.id)

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, fish_name, value FROM user_inventory WHERE user_id = ?", (interaction.user.id,)) as cur:
            fishes = await cur.fetchall()

        if not fishes:
            return await interaction.response.send_message("❌ Dein Eimer ist komplett leer! Geh zuerst angeln.", ephemeral=True)

        if profile["bucket_flipped"] == 1:
            return await interaction.response.send_message(
                "🛑 **Dieser Eimer wurde bereits gecoinflippt!**\n"
                "Ein Eimer kann nur genau **einmal** riskiert werden. Verkaufe deine Fische mit `/verkaufen`, um mit neuem Fang wieder flippen zu können.",
                ephemeral=True
            )

        win = random.choice([True, False])

        if win:
            await db.execute("UPDATE user_inventory SET value = value * 2 WHERE user_id = ?", (interaction.user.id,))
            await db.execute("UPDATE user_profiles SET bucket_flipped = 1 WHERE user_id = ?", (interaction.user.id,))
            await db.commit()

            embed = discord.Embed(
                title="🪙 COINFLIP GEWONNEN! 🎉",
                description=f"Die Münze landete auf deiner Seite! Der Marktwert aller **{len(fishes)} Fische** in deinem Eimer wurde **VERDOPPELT** ($2\\times$)!",
                color=discord.Color.gold()
            )
            embed.set_footer(text="Dieser Eimer ist nun gesperrt für weitere Flips. Verkaufe ihn im Hafen!")
            await interaction.response.send_message(embed=embed)
        else:
            await db.execute("DELETE FROM user_inventory WHERE user_id = ?", (interaction.user.id,))
            await db.execute("UPDATE user_profiles SET bucket_flipped = 0 WHERE user_id = ?", (interaction.user.id,))
            await db.commit()

            embed = discord.Embed(
                title="🪙 COINFLIP VERLOREN! 💀",
                description=f"Pech gehabt! Die Münze fiel gegen dich. Dein gesamter Eimer mit **{len(fishes)} Fischen** ist im Meer versunken!",
                color=discord.Color.red()
            )
            embed.set_footer(text="Alles verloren. Kaufe neue Köder und versuche dein Glück erneut!")
            await interaction.response.send_message(embed=embed)

# ==========================================
# 7. HAFENMARKT (15 MIN COOLDOWN & ±100%)
# ==========================================
class DynamicMarketView(discord.ui.View):
    def __init__(self, user_id: int, fish_bonus_pct: int, npc_name: str):
        super().__init__(timeout=60.0)
        self.user_id = user_id
        self.fish_bonus_pct = fish_bonus_pct
        self.npc_name = npc_name

    @discord.ui.button(label="Fische mit Händler-Kurs verkaufen", emoji="💰", style=discord.ButtonStyle.success)
    async def sell_bonus(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Das ist nicht dein Händler!", ephemeral=True)

        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("""
                SELECT SUM(value), COUNT(id) FROM user_inventory 
                WHERE user_id = ? AND fish_rarity NOT IN ('Mystisch', 'Ultraselten')
            """, (self.user_id,)) as cur:
                row = await cur.fetchone()
                base_earned = row[0] or 0
                count = row[1] or 0

            if count == 0:
                return await interaction.response.send_message("Keine regulären Fische im Eimer!", ephemeral=True)

            multiplier = max(0.0, 1.0 + (self.fish_bonus_pct / 100.0))
            gross_earned = int(base_earned * multiplier)

            await db.execute("DELETE FROM user_inventory WHERE user_id = ? AND fish_rarity NOT IN ('Mystisch', 'Ultraselten')", (self.user_id,))
            tax_info = await distribute_family_income(db, self.user_id, gross_earned)
            await db.execute("UPDATE user_profiles SET bucket_flipped = 0 WHERE user_id = ?", (self.user_id,))
            await db.commit()

        gross_str = f"{gross_earned:,}".replace(",", ".")
        net_str = f"{tax_info['net']:,}".replace(",", ".")
        fam_note = format_family_note(tax_info)

        msg = (
            f"🤝 **Handel abgeschlossen!** {self.npc_name} zahlte dir **{gross_str} 🪙** brutto für {count} Fische ({self.fish_bonus_pct:+d}% Marktkurs).\n"
            f"💵 **Dein Nettoerlös:** **+{net_str} 🪙**"
        )
        if fam_note:
            msg += f"\n{fam_note}"

        await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="hafenmarkt", description="Triff auf einen Händler mit extremen Preisschwankungen (15 Min. Cooldown!).")
@app_commands.checks.cooldown(1, 900.0, key=lambda i: (i.guild_id, i.user.id))
async def harbor_market(interaction: discord.Interaction):
    npc = f"{random.choice(NPC_FIRST_NAMES)} {random.choice(NPC_LAST_NAMES)}"
    fish_bonus = random.randint(-100, 100)

    if fish_bonus >= 50:
        mood = "ist in absoluter Kauflust und zahlt exorbitante Mondpreise!"
    elif fish_bonus > 0:
        mood = "zahlt heute überdurchschnittlich gut."
    elif fish_bonus == -100:
        mood = "will dich komplett ausrauben (zahlt 0 🪙 für deinen Fang)!"
    else:
        mood = "ist extrem geizig und drückt die Preise in den Keller."

    embed = discord.Embed(
        title=f"⚓ Hafenmarkt: {npc}",
        description=f"Ein Händler ist am Kai aufgetaucht und {mood}\n*Sein Angebot gilt nur für diese Interaktion.*",
        color=discord.Color.teal() if fish_bonus >= 0 else discord.Color.dark_red()
    )
    embed.add_field(name="🐟 Tages-Ankaufkurs", value=f"**{fish_bonus:+d}%** auf alle regulären Fische!", inline=False)
    embed.set_footer(text="Cooldown: 15 Minuten | Automatische Abgaben: 25% Ehepartner, 5% Kinder")

    view = DynamicMarketView(interaction.user.id, fish_bonus, npc)
    await interaction.response.send_message(embed=embed, view=view)

@harbor_market.error
async def harbor_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        minutes = int(error.retry_after // 60)
        seconds = int(error.retry_after % 60)
        await interaction.response.send_message(
            f"⏳ Der Hafenmarkt ist leergefegt! Ein neuer Händler legt erst in **{minutes}m {seconds}s** an.",
            ephemeral=True
        )

# ==========================================
# 8. VERKAUFEN MIT AUTOMATISCHEN FAMILIENABGABEN
# ==========================================
@bot.tree.command(name="verkaufen", description="Verkaufe Fische aus deinem Eimer (25% an Ehepartner, 5% an Kinder).")
@app_commands.describe(einzigartige_mitverkaufen="Auf 'True' setzen, um auch Mystische & Ultraseltene Karten zu verkaufen!")
async def sell(interaction: discord.Interaction, einzigartige_mitverkaufen: bool = False):
    async with aiosqlite.connect(DB_NAME) as db:
        if einzigartige_mitverkaufen:
            query = "SELECT SUM(value), COUNT(id) FROM user_inventory WHERE user_id = ?"
            del_query = "DELETE FROM user_inventory WHERE user_id = ?"
        else:
            query = "SELECT SUM(value), COUNT(id) FROM user_inventory WHERE user_id = ? AND fish_rarity NOT IN ('Mystisch', 'Ultraselten')"
            del_query = "DELETE FROM user_inventory WHERE user_id = ? AND fish_rarity NOT IN ('Mystisch', 'Ultraselten')"

        async with db.execute(query, (interaction.user.id,)) as cur:
            row = await cur.fetchone()
            gross_earned = row[0] or 0
            count = row[1] or 0

        if count == 0:
            if not einzigartige_mitverkaufen:
                return await interaction.response.send_message("Keine regulären Fische vorhanden! Nutze `/verkaufen einzigartige_mitverkaufen:True` oder `/verkaufe_einzeln` für Sammelkarten.", ephemeral=True)
            return await interaction.response.send_message("Dein Eimer ist komplett leer!", ephemeral=True)

        await db.execute(del_query, (interaction.user.id,))
        tax_info = await distribute_family_income(db, interaction.user.id, gross_earned)
        await db.execute("UPDATE user_profiles SET bucket_flipped = 0 WHERE user_id = ?", (interaction.user.id,))
        await db.commit()

    gross_str = f"{gross_earned:,}".replace(",", ".")
    net_str = f"{tax_info['net']:,}".replace(",", ".")
    fam_note = format_family_note(tax_info)

    msg = f"💰 Du hast **{count}** Fische für **{gross_str} 🪙** brutto verkauft! (Dein Nettoerlös: **+{net_str} 🪙**)"
    if fam_note:
        msg += f"\n{fam_note}"
    if einzigartige_mitverkaufen:
        msg += "\n⚠️ *Hinweis: Deine Trophäen- und Sammelkarten wurden ebenfalls verkauft.*"

    await interaction.response.send_message(msg)

@bot.tree.command(name="verkaufe_einzeln", description="Verkaufe gezielt eine bestimmte Trophäe oder einen einzelnen Fisch.")
async def sell_single(interaction: discord.Interaction, fisch_name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT id, fish_name, fish_rarity, fish_weight, value 
            FROM user_inventory WHERE user_id = ? AND LOWER(fish_name) LIKE LOWER(?) LIMIT 1
        """, (interaction.user.id, f"%{fisch_name}%")) as cur:
            fish_row = await cur.fetchone()

        if not fish_row:
            return await interaction.response.send_message(f"❌ Kein Fisch namens `{fisch_name}` im Inventar!", ephemeral=True)

        fish_id, real_name, rarity, weight, gross_val = fish_row
        await db.execute("DELETE FROM user_inventory WHERE id = ?", (fish_id,))
        tax_info = await distribute_family_income(db, interaction.user.id, gross_val)
        await db.commit()

    gross_str = f"{gross_val:,}".replace(",", ".")
    net_str = f"{tax_info['net']:,}".replace(",", ".")
    fam_note = format_family_note(tax_info)

    msg = f"🏷️ Du hast **{real_name}** ({rarity}, {weight} kg) für **{gross_str} 🪙** brutto an einen Sammler abgegeben! (Netto: **+{net_str} 🪙**)"
    if fam_note:
        msg += f"\n{fam_note}"

    await interaction.response.send_message(msg)

# ==========================================
# 9. SAMMELKARTEN & HANDEL
# ==========================================
@bot.tree.command(name="sammelkarte", description="Betrachte eine ausgestellte Sammelkarte im Detail.")
async def card_view(interaction: discord.Interaction, name_des_fisches: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT id, user_id, fish_name, fish_rarity, fish_weight, value, original_catcher_id 
            FROM user_inventory 
            WHERE LOWER(fish_name) LIKE LOWER(?) AND fish_rarity IN ('Mystisch', 'Ultraselten')
            LIMIT 1
        """, (f"%{name_des_fisches}%",)) as cur:
            row = await cur.fetchone()

    if not row:
        return await interaction.response.send_message(f"❌ Keine ausgestellte Sammelkarte für `{name_des_fisches}` gefunden!", ephemeral=True)

    _, owner_id, fish_name, rarity, weight, val, original_catcher_id = row
    img_url, subtitle = get_card_data(fish_name)

    catcher_mention = f"<@{original_catcher_id}>" if original_catcher_id else "*Unbekannter Erstfänger*"
    owner_mention = f"<@{owner_id}>"

    embed = discord.Embed(
        title=f"🃏 SAMMELKARTE: {fish_name}",
        description=f"*{subtitle or 'Extrem seltene Trophäe'}*",
        color=discord.Color.from_rgb(241, 196, 15)
    )
    if img_url:
        embed.set_image(url=img_url)

    embed.add_field(name="Seltenheit", value=f"⭐ {rarity}", inline=True)
    embed.add_field(name="Gewicht", value=f"{weight} kg", inline=True)
    embed.add_field(name="Wert", value=f"{val:,} 🪙".replace(",", "."), inline=True)
    embed.add_field(name="🎣 Ursprünglich geangelt von", value=catcher_mention, inline=False)
    embed.add_field(name="👤 Aktueller Besitzer", value=owner_mention, inline=False)
    embed.set_footer(text="Handelbar mit /verschenke_fisch | Unveränderlicher Erstfänger-Eintrag")

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="verschenke_fisch", description="Übertrage einen Fisch an einen anderen Spieler.")
async def gift_fish(interaction: discord.Interaction, empfaenger: discord.Member, fisch_name: str):
    if empfaenger.id == interaction.user.id or empfaenger.bot:
        return await interaction.response.send_message("Ungültiger Empfänger!", ephemeral=True)

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT id, fish_name, fish_rarity, fish_weight, original_catcher_id FROM user_inventory 
            WHERE user_id = ? AND LOWER(fish_name) LIKE LOWER(?) LIMIT 1
        """, (interaction.user.id, f"%{fisch_name}%")) as cur:
            fish_row = await cur.fetchone()

        if not fish_row:
            return await interaction.response.send_message(f"Du besitzt keinen Fisch namens `{fisch_name}`!", ephemeral=True)

        fish_id, real_name, rarity, weight, orig_id = fish_row
        await db.execute("UPDATE user_inventory SET user_id = ? WHERE id = ?", (empfaenger.id, fish_id))
        await db.commit()

    await interaction.response.send_message(
        f"🎁 {interaction.user.mention} hat **{real_name}** an {empfaenger.mention} übergeben!\n"
        f"*(Der Erstfänger-Vermerk <@{orig_id}> bleibt auf der Sammelkarte fest eingraviert!)*"
    )

# ==========================================
# 10. KÖDER- & UPGRADE-SHOP
# ==========================================
class BaitSelect(discord.ui.Select):
    def __init__(self, user_id: int):
        self.user_id = user_id
        options = []
        for tier_id, t in BAIT_TIERS.items():
            cost_str = f"{t['cost_pack']:,}".replace(",", ".")
            options.append(discord.SelectOption(
                label=f"Stufe {tier_id}: {t['name']} ({cost_str} 🪙)",
                value=str(tier_id),
                description=f"{t['amount']}x Köder | {t['desc'][:45]}",
                emoji=t["emoji"]
            ))
        super().__init__(placeholder="Wähle deine Köderstufe zum Kaufen...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Das ist nicht dein Menü!", ephemeral=True)

        tier_id = int(self.values[0])
        tier_data = BAIT_TIERS[tier_id]
        profile = await get_profile(self.user_id)

        if profile["coins"] < tier_data["cost_pack"]:
            return await interaction.response.send_message(f"❌ Zu wenig Münzen! Kostet **{tier_data['cost_pack']} 🪙**.", ephemeral=True)

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                UPDATE user_profiles 
                SET coins = coins - ?, baits = baits + ?, bait_tier = ? 
                WHERE user_id = ?
            """, (tier_data["cost_pack"], tier_data["amount"], tier_id, self.user_id))
            await db.commit()

        await interaction.response.send_message(
            f"✅ **{tier_data['amount']}x {tier_data['name']}** gekauft und ausgerüstet! (Aktive Köderstufe: **Stufe {tier_id}**)",
            ephemeral=True
        )

class ShopView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=90.0)
        self.user_id = user_id
        self.add_item(BaitSelect(user_id))

    @discord.ui.button(label="Rute aufwerten", emoji="🎣", style=discord.ButtonStyle.success)
    async def upgrade_rod(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Das ist nicht dein Shop!", ephemeral=True)

        profile = await get_profile(self.user_id)
        next_level = profile["rod_level"] + 1

        if next_level not in RODS:
            return await interaction.response.send_message("⭐ Du besitzt bereits die beste Rute im Spiel!", ephemeral=True)

        next_rod = RODS[next_level]
        if profile["coins"] < next_rod["cost"]:
            cost_str = f"{next_rod['cost']:,}".replace(",", ".")
            return await interaction.response.send_message(f"❌ Du benötigst **{cost_str} 🪙**!", ephemeral=True)

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE user_profiles SET coins = coins - ?, rod_level = ? WHERE user_id = ?", (next_rod["cost"], next_level, self.user_id))
            await db.commit()

        await interaction.response.send_message(f"🎉 **{next_rod['name']}** erfolgreich gekauft und montiert!", ephemeral=True)

@bot.tree.command(name="shop", description="Kaufe hochwertige Köderstufen und mächtige Angelruten.")
async def shop(interaction: discord.Interaction):
    profile = await get_profile(interaction.user.id)
    curr_tier = BAIT_TIERS.get(profile["bait_tier"], BAIT_TIERS[1])
    next_level = profile["rod_level"] + 1

    embed = discord.Embed(
        title="🛒 Hafen-Ausrüster: Köder & Ruten",
        description="Wähle eine Köderstufe aus dem Menü unten. Bessere Köder schalten seltenere Fische frei!",
        color=discord.Color.gold()
    )
    coins_str = f"{profile['coins']:,}".replace(",", ".")
    embed.add_field(name="Guthaben", value=f"{coins_str} 🪙", inline=True)
    embed.add_field(name="Aktueller Köder", value=f"{curr_tier['emoji']} Stufe {profile['bait_tier']} ({profile['baits']} übrig)", inline=True)

    if next_level in RODS:
        nr = RODS[next_level]
        cost_str = f"{nr['cost']:,}".replace(",", ".")
        embed.add_field(name="🎣 Nächste Rute", value=f"**{nr['name']}** ({cost_str} 🪙)", inline=True)
    else:
        embed.add_field(name="🎣 Nächste Rute", value="Maximalstufe!", inline=True)

    bait_overview = []
    for tid, t in BAIT_TIERS.items():
        c_str = f"{t['cost_pack']:,}".replace(",", ".")
        bait_overview.append(f"• **Stufe {tid} ({t['name']}):** {t['amount']}x für {c_str} 🪙 | *{t['desc']}*")
    embed.add_field(name="Köderstufen-Katalog", value="\n".join(bait_overview), inline=False)

    await interaction.response.send_message(embed=embed, view=ShopView(interaction.user.id))

# ==========================================
# 11. UNTERNEHMEN & DIVIDENDEN
# ==========================================
class BusinessGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="business", description="Errichte und verwalte dein Wirtschaftsimperium")

    @app_commands.command(name="gruenden", description="Gründe ein eigenes Unternehmen (hohes Kapital nötig).")
    async def create_biz(self, interaction: discord.Interaction, typ: str, firmenname: str):
        if typ.lower() not in BUSINESS_TYPES:
            types_list = ", ".join([f"`{k}`" for k in BUSINESS_TYPES.keys()])
            return await interaction.response.send_message(f"Ungültiger Typ! Wähle aus: {types_list}", ephemeral=True)

        biz_data = BUSINESS_TYPES[typ.lower()]
        profile = await get_profile(interaction.user.id)

        if profile["coins"] < biz_data["cost"]:
            cost_str = f"{biz_data['cost']:,}".replace(",", ".")
            user_coins_str = f"{profile['coins']:,}".replace(",", ".")
            return await interaction.response.send_message(
                f"❌ Du benötigst **{cost_str} 🪙** für diese Gründung (Du hast: {user_coins_str} 🪙).",
                ephemeral=True
            )

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE user_profiles SET coins = coins - ? WHERE user_id = ?", (biz_data["cost"], interaction.user.id))
            cursor = await db.execute("""
                INSERT INTO businesses (owner_id, business_type, custom_name)
                VALUES (?, ?, ?)
            """, (interaction.user.id, typ.lower(), firmenname))
            biz_id = cursor.lastrowid
            await db.execute("""
                INSERT INTO business_shares (business_id, user_id, shares_owned)
                VALUES (?, ?, 50)
            """, (biz_id, interaction.user.id))
            await db.commit()

        embed = discord.Embed(
            title="🏢 Großunternehmens-Gründung vollzogen!",
            description=f"Herzlichen Glückwunsch! Du bist nun Eigentümer von **{firmenname}** (ID: `#{biz_id}`).",
            color=discord.Color.gold()
        )
        embed.add_field(name="Branche", value=biz_data["name"], inline=True)
        embed.add_field(name="Deine Anteile", value="50 / 100 (Mehrheitseigner)", inline=True)
        embed.add_field(name="Freie Anteile", value="50 Anteile für Investoren", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="liste", description="Zeige alle aktiven Unternehmen auf dem Server.")
    async def list_biz(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("""
                SELECT b.id, b.custom_name, b.business_type, b.owner_id, IFNULL(SUM(s.shares_owned), 0)
                FROM businesses b LEFT JOIN business_shares s ON b.id = s.business_id GROUP BY b.id
            """) as cur:
                rows = await cur.fetchall()

        if not rows:
            return await interaction.response.send_message("Noch keine Unternehmen gegründet!", ephemeral=True)

        embed = discord.Embed(title="📈 Wirtschaftskammer: Aktive Unternehmen", color=discord.Color.dark_teal())
        for b_id, name, b_type, owner_id, total_sold in rows:
            free_shares = 100 - total_sold
            embed.add_field(
                name=f"#{b_id} — {name}",
                value=f"• Branche: {BUSINESS_TYPES[b_type]['name']}\n• Inhaber: <@{owner_id}>\n• Freie Anteile: **{free_shares}/100**",
                inline=False
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ausschuetten", description="Erwirtschafte Erträge und schütte Dividenden an alle Investoren aus.")
    async def payout(self, interaction: discord.Interaction, firmen_id: int):
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT owner_id, business_type, custom_name FROM businesses WHERE id = ?", (firmen_id,)) as cur:
                biz = await cur.fetchone()

            if not biz:
                return await interaction.response.send_message("Unternehmen nicht gefunden!", ephemeral=True)

            owner_id, b_type, custom_name = biz
            if interaction.user.id != owner_id:
                return await interaction.response.send_message("Nur der Inhaber kann Dividenden ausschütten!", ephemeral=True)

            b_info = BUSINESS_TYPES[b_type]
            total_profit = random.randint(b_info["base_yield_min"], b_info["base_yield_max"])

            async with db.execute("SELECT user_id, shares_owned FROM business_shares WHERE business_id = ?", (firmen_id,)) as cur:
                shareholders = await cur.fetchall()

            payout_summary = []
            for u_id, shares in shareholders:
                user_gross = int(total_profit * (shares / 100))
                if user_gross > 0:
                    tax_info = await distribute_family_income(db, u_id, user_gross)
                    cut_str = f"{tax_info['net']:,}".replace(",", ".")
                    payout_summary.append(f"<@{u_id}>: **+{cut_str} 🪙** netto ({shares}%)")

            await db.commit()

        total_str = f"{total_profit:,}".replace(",", ".")
        embed = discord.Embed(
            title=f"💸 Dividendenausschüttung: {custom_name}",
            description=f"Das Unternehmen erwirtschaftete einen Gesamtgewinn von **{total_str} 🪙**! *(Familienabgaben wurden automatisch abgezogen)*",
            color=discord.Color.green()
        )
        embed.add_field(name="Netto-Ausschüttung nach Anteilen", value="\n".join(payout_summary) or "Keine Investoren", inline=False)
        await interaction.response.send_message(embed=embed)

bot.tree.add_command(BusinessGroup())

@bot.tree.command(name="investieren", description="Kaufe Anteile an einem existierenden Unternehmen (Preis: 5.000 🪙 pro Anteil).")
async def invest(interaction: discord.Interaction, firmen_id: int, anzahl_anteile: int):
    if anzahl_anteile <= 0:
        return await interaction.response.send_message("Die Anzahl muss mindestens 1 betragen!", ephemeral=True)

    share_price = 5000
    total_cost = anzahl_anteile * share_price
    profile = await get_profile(interaction.user.id)

    if profile["coins"] < total_cost:
        cost_str = f"{total_cost:,}".replace(",", ".")
        return await interaction.response.send_message(f"❌ Du benötigst **{cost_str} 🪙** für {anzahl_anteile} Anteile!", ephemeral=True)

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT custom_name FROM businesses WHERE id = ?", (firmen_id,)) as cur:
            biz = await cur.fetchone()
        if not biz:
            return await interaction.response.send_message("Unternehmen nicht gefunden!", ephemeral=True)

        async with db.execute("SELECT IFNULL(SUM(shares_owned), 0) FROM business_shares WHERE business_id = ?", (firmen_id,)) as cur:
            sold_shares = (await cur.fetchone())[0]

        if sold_shares + anzahl_anteile > 100:
            return await interaction.response.send_message(f"❌ Es sind nur noch **{100 - sold_shares}** Anteile frei!", ephemeral=True)

        await db.execute("UPDATE user_profiles SET coins = coins - ? WHERE user_id = ?", (total_cost, interaction.user.id))
        await db.execute("""
            INSERT INTO business_shares (business_id, user_id, shares_owned)
            VALUES (?, ?, ?)
            ON CONFLICT(business_id, user_id) DO UPDATE SET shares_owned = shares_owned + excluded.shares_owned
        """, (firmen_id, interaction.user.id, anzahl_anteile))
        await db.commit()

    cost_str = f"{total_cost:,}".replace(",", ".")
    await interaction.response.send_message(
        f"📈 Erfolgreich **{anzahl_anteile} Anteile** an **{biz[0]}** für **{cost_str} 🪙** gekauft! Du wirst an künftigen Gewinnen beteiligt."
    )

# ==========================================
# 12. PROFIL, HEIRAT & ADOPTION
# ==========================================
class MarriageView(discord.ui.View):
    def __init__(self, requester: discord.Member, target: discord.Member):
        super().__init__(timeout=120.0)
        self.requester = requester
        self.target = target

    @discord.ui.button(label="Ja, ich will! 💍", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("Das ist nicht dein Heiratsantrag!", ephemeral=True)

        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT id FROM user_rpg_items WHERE user_id = ? AND item_key = 'ring'", (self.requester.id,)) as cur:
                ring_entry = await cur.fetchone()
                if not ring_entry:
                    return await interaction.response.send_message("Der Ring ist auf wundersame Weise verschwunden!", ephemeral=True)

            await db.execute("DELETE FROM user_rpg_items WHERE id = ?", (ring_entry[0],))
            await db.execute("UPDATE user_profiles SET spouse_id = ? WHERE user_id = ?", (self.target.id, self.requester.id))
            await db.execute("UPDATE user_profiles SET spouse_id = ? WHERE user_id = ?", (self.requester.id, self.target.id))
            await db.commit()

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content=f"💒 **HERZLICHEN GLÜCKWUNSCH!** {self.target.mention} hat den Antrag von {self.requester.mention} angenommen! Beide erhalten ab sofort 25% der Einnahmen des jeweils anderen!",
            view=self
        )

    @discord.ui.button(label="Ablehnen 💔", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("Das ist nicht dein Antrag!", ephemeral=True)

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=f"💔 {self.target.mention} hat den Antrag von {self.requester.mention} abgelehnt.", view=self)

@bot.tree.command(name="heiraten", description="Mache jemandem einen Heiratsantrag (benötigt einen Ehering).")
async def marry(interaction: discord.Interaction, partner: discord.Member):
    if partner.id == interaction.user.id or partner.bot:
        return await interaction.response.send_message("Du kannst dich nicht selbst oder Bots heiraten!", ephemeral=True)

    author_data = await get_profile(interaction.user.id)
    target_data = await get_profile(partner.id)

    if author_data["spouse_id"]:
        return await interaction.response.send_message("Du bist bereits verheiratet! Nutze `/scheidung`, falls nötig.", ephemeral=True)
    if target_data["spouse_id"]:
        return await interaction.response.send_message(f"{partner.mention} ist bereits vergeben!", ephemeral=True)

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id FROM user_rpg_items WHERE user_id = ? AND item_key = 'ring'", (interaction.user.id,)) as cur:
            if not await cur.fetchone():
                return await interaction.response.send_message("❌ Du besitzt keinen **💍 Ehering**! Kaufe zuerst einen im `/rpgshop`.", ephemeral=True)

    view = MarriageView(interaction.user, partner)
    await interaction.response.send_message(
        f"💍 {partner.mention}, **{interaction.user.mention}** kniet nieder und macht dir einen Heiratsantrag! Nimmst du an?",
        view=view
    )

@bot.tree.command(name="scheidung", description="Lasse dich von deinem Ehepartner scheiden.")
async def divorce(interaction: discord.Interaction):
    data = await get_profile(interaction.user.id)
    if not data["spouse_id"]:
        return await interaction.response.send_message("Du bist gar nicht verheiratet!", ephemeral=True)

    spouse_id = data["spouse_id"]
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE user_profiles SET spouse_id = NULL WHERE user_id = ?", (interaction.user.id,))
        await db.execute("UPDATE user_profiles SET spouse_id = NULL WHERE user_id = ?", (spouse_id,))
        await db.commit()

    await interaction.response.send_message(f"💔 Du hast dich von <@{spouse_id}> scheiden lassen. Die 25% Ehepartner-Beteiligung ist beendet.")

class AdoptView(discord.ui.View):
    def __init__(self, parent: discord.Member, child: discord.Member):
        super().__init__(timeout=120.0)
        self.parent = parent
        self.child = child

    @discord.ui.button(label="Ich nehme an! 🧸", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.child.id:
            return await interaction.response.send_message("Das ist nicht deine Adoptionsanfrage!", ephemeral=True)

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE user_profiles SET parent_id = ? WHERE user_id = ?", (self.parent.id, self.child.id))
            await db.commit()

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content=f"👨‍👧‍👦 **Familienzuwachs!** {self.child.mention} wurde von {self.parent.mention} adoptiert und erhält ab sofort 5% Taschengeld auf alle Einnahmen!",
            view=self
        )

    @discord.ui.button(label="Nein danke ❌", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.child.id:
            return await interaction.response.send_message("Das ist nicht deine Anfrage!", ephemeral=True)

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=f"❌ {self.child.mention} möchte nicht adoptiert werden.", view=self)

@bot.tree.command(name="adoptieren", description="Adoptiere ein Mitglied als dein Kind (erhält 5% Taschengeld deiner Einnahmen).")
async def adopt(interaction: discord.Interaction, kind: discord.Member):
    if kind.id == interaction.user.id or kind.bot:
        return await interaction.response.send_message("Du kannst dich nicht selbst oder Bots adoptieren!", ephemeral=True)

    child_data = await get_profile(kind.id)
    if child_data["parent_id"]:
        return await interaction.response.send_message(f"{kind.mention} hat bereits ein Elternteil (<@{child_data['parent_id']}>)!", ephemeral=True)

    view = AdoptView(interaction.user, kind)
    await interaction.response.send_message(f"🍼 {kind.mention}, **{interaction.user.mention}** möchte dich gerne adoptieren! Stimmst du zu?", view=view)

@bot.tree.command(name="entlassen", description="Entlasse dein Kind oder verlasse deine Familie.")
async def disown(interaction: discord.Interaction, kind: discord.Member = None):
    async with aiosqlite.connect(DB_NAME) as db:
        if kind:
            await db.execute("UPDATE user_profiles SET parent_id = NULL WHERE user_id = ? AND parent_id = ?", (kind.id, interaction.user.id))
            await db.commit()
            await interaction.response.send_message(f"Du hast {kind.mention} aus deiner Familie entlassen (Taschengeld beendet).")
        else:
            await db.execute("UPDATE user_profiles SET parent_id = NULL WHERE user_id = ?", (interaction.user.id,))
            await db.commit()
            await interaction.response.send_message("Du hast deine Familie verlassen und stehst nun auf eigenen Beinen.")

@bot.tree.command(name="profil", description="Zeige dein Profil, Beziehungen, Betriebe und Trophäenkarten.")
async def profile_cmd(interaction: discord.Interaction, mitglied: discord.Member = None):
    target = mitglied or interaction.user
    data = await get_profile(target.id)
    rod = RODS[data["rod_level"]]
    bait = BAIT_TIERS.get(data["bait_tier"], BAIT_TIERS[1])

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT item_key FROM user_rpg_items WHERE user_id = ?", (target.id,)) as cur:
            user_items = [row[0] for row in await cur.fetchall()]

        async with db.execute("SELECT user_id FROM user_profiles WHERE parent_id = ?", (target.id,)) as cur:
            children_ids = [row[0] for row in await cur.fetchall()]

        async with db.execute("SELECT custom_name FROM businesses WHERE owner_id = ?", (target.id,)) as cur:
            owned_biz = [row[0] for row in await cur.fetchall()]

        async with db.execute("""
            SELECT fish_name, original_catcher_id FROM user_inventory 
            WHERE user_id = ? AND fish_rarity IN ('Mystisch', 'Ultraselten')
        """, (target.id,)) as cur:
            trophy_rows = await cur.fetchall()

    embed = discord.Embed(title=f"📜 Bürger- & Anglerakte: {target.display_name}", color=discord.Color.blue())
    embed.set_thumbnail(url=target.display_avatar.url)

    spouse_text = f"<@{data['spouse_id']}> 💕 (25% Beteiligung)" if data["spouse_id"] else "*Ledig*"
    parent_text = f"<@{data['parent_id']}>" if data["parent_id"] else "*Keine*"
    children_text = ", ".join([f"<@{cid}>" for cid in children_ids]) + " (5% Taschengeld)" if children_ids else "*Keine*"

    embed.add_field(name="💍 Ehepartner", value=spouse_text, inline=True)
    embed.add_field(name="👨‍👧 Elternteil", value=parent_text, inline=True)
    embed.add_field(name="🧸 Kinder", value=children_text, inline=True)

    coins_str = f"{data['coins']:,}".replace(",", ".")
    embed.add_field(name="🪙 Goldmünzen", value=coins_str, inline=True)
    embed.add_field(name="🎣 Angelrute", value=f"{rod['name']}", inline=True)
    embed.add_field(name="🪱 Aktiver Köder", value=f"{bait['emoji']} {bait['name']} ({data['baits']}x)", inline=True)

    # Alle 7 Verzauberungen übersichtlich anzeigen
    ench_lines = []
    if data["ench_luck"] > 0:
        ench_lines.append(f"✨ **Glück des Meeres {data['ench_luck']}** (+{int((ENCHANTMENTS['luck']['levels'][data['ench_luck']]['bonus']-1)*100)}%)")
    if data["ench_lure_save"] > 0:
        ench_lines.append(f"🪱 **Köder-Sparer {data['ench_lure_save']}** ({int(ENCHANTMENTS['lure_save']['levels'][data['ench_lure_save']]['chance']*100)}% Chance)")
    if data["ench_treasure"] > 0:
        ench_lines.append("🏴‍☠️ **Schatzsucher** (Münztruhen beim Angeln)")
    if data["ench_giant"] > 0:
        ench_lines.append(f"⚖️ **Giganten-Köder {data['ench_giant']}** (+{int((ENCHANTMENTS['giant']['levels'][data['ench_giant']]['mult']-1)*100)}% Gewicht)")
    if data["ench_double"] > 0:
        ench_lines.append(f"🪞 **Doppel-Haken {data['ench_double']}** ({int(ENCHANTMENTS['double']['levels'][data['ench_double']]['chance']*100)}% Chance)")
    if data["ench_purity"] > 0:
        ench_lines.append("🌊 **Neptuns Segen** (Kein Müll)")
    if data["ench_haste"] > 0:
        cd_s = 6 if data["ench_haste"] == 1 else 3
        ench_lines.append(f"⚡ **Blitz-Reflexe {data['ench_haste']}** ({cd_s}s Cooldown)")

    embed.add_field(name="🔮 Aktive Verzauberungen", value="\n".join(ench_lines) if ench_lines else "*Keine Verzauberungen aktiv*", inline=False)

    if owned_biz:
        embed.add_field(name="🏢 Firmeneigentümer von", value=", ".join(owned_biz), inline=False)

    if user_items:
        items_str = "\n".join([COMMUNITY_SHOP_ITEMS[k]["name"] for k in user_items if k in COMMUNITY_SHOP_ITEMS])
        embed.add_field(name="🏛️ Statussymbole", value=items_str, inline=False)

    if trophy_rows:
        trophy_str = []
        for f_name, orig_id in trophy_rows[:8]:
            orig_tag = f"*(Erstfang: <@{orig_id}>)*" if orig_id else ""
            trophy_str.append(f"• **{f_name}** {orig_tag}")
        embed.add_field(name="🃏 Ausgestellte Sammelkarten & Trophäen", value="\n".join(trophy_str), inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="inventar", description="Zeige deine gefangenen Fische im Eimer.")
async def inventory(interaction: discord.Interaction):
    profile = await get_profile(interaction.user.id)
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT fish_name, fish_rarity, fish_weight, value FROM user_inventory 
            WHERE user_id = ? ORDER BY id DESC LIMIT 10
        """, (interaction.user.id,)) as cur:
            fishes = await cur.fetchall()

    flip_status = "⚠️ Bereits geflippt ($2\\times$)" if profile["bucket_flipped"] == 1 else "Bereit für `/coinflip_eimer`"
    embed = discord.Embed(title=f"🎒 Eimer von {interaction.user.display_name}", color=discord.Color.teal())
    coins_str = f"{profile['coins']:,}".replace(",", ".")
    embed.add_field(name="Münzen", value=f"{coins_str} 🪙", inline=True)
    embed.add_field(name="Eimer-Status", value=flip_status, inline=True)

    if fishes:
        fish_list = "\n".join([f"• **{f[0]}** ({f[1]}) - {f[2]} kg | Wert: {f[3]:,} 🪙".replace(",", ".") for f in fishes])
        embed.add_field(name="Letzte Fänge (max. 10)", value=fish_list, inline=False)
    else:
        embed.add_field(name="Inhalt", value="*Dein Eimer ist leer.*", inline=False)

    await interaction.response.send_message(embed=embed)

# ==========================================
# 13. RPG-SHOP & VERZAUBERMEISTER MIT SELECT-MENÜ
# ==========================================
class RPGShopSelect(discord.ui.Select):
    def __init__(self, user_id: int):
        self.user_id = user_id
        options = [
            discord.SelectOption(
                label=f"{item['name']} ({item['cost']:,} 🪙)".replace(",", "."),
                value=key,
                description=item["desc"][:50]
            )
            for key, item in COMMUNITY_SHOP_ITEMS.items()
        ]
        super().__init__(placeholder="Wähle ein Item zum Kaufen...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Nutze deinen eigenen Shop!", ephemeral=True)
        item_key = self.values[0]
        item_data = COMMUNITY_SHOP_ITEMS[item_key]

        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT id FROM user_rpg_items WHERE user_id = ? AND item_key = ?", (self.user_id, item_key)) as cur:
                if await cur.fetchone() and item_key != "ring":
                    return await interaction.response.send_message("❌ Dieses Item besitzt du bereits!", ephemeral=True)
            async with db.execute("SELECT coins FROM user_profiles WHERE user_id = ?", (self.user_id,)) as cur:
                coins = (await cur.fetchone())[0]
            if coins < item_data["cost"]:
                cost_str = f"{item_data['cost']:,}".replace(",", ".")
                return await interaction.response.send_message(f"❌ Kostet **{cost_str} 🪙**!", ephemeral=True)
            await db.execute("UPDATE user_profiles SET coins = coins - ? WHERE user_id = ?", (item_data["cost"], self.user_id))
            await db.execute("INSERT INTO user_rpg_items (user_id, item_key) VALUES (?, ?)", (self.user_id, item_key))
            await db.commit()
        await interaction.response.send_message(f"🎉 **{item_data['name']}** gekauft!", ephemeral=True)

class RPGShopView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60.0)
        self.add_item(RPGShopSelect(user_id))

@bot.tree.command(name="rpgshop", description="Kaufe Eheringe, Häuser und Statussymbole.")
async def rpg_shop(interaction: discord.Interaction):
    profile = await get_profile(interaction.user.id)
    embed = discord.Embed(title="🏛️ Community- & RPG-Markt", color=discord.Color.dark_gold())
    for _, item in COMMUNITY_SHOP_ITEMS.items():
        cost_str = f"{item['cost']:,}".replace(",", ".")
        embed.add_field(name=f"{item['name']} — {cost_str} 🪙", value=item["desc"], inline=False)
    coins_str = f"{profile['coins']:,}".replace(",", ".")
    embed.set_footer(text=f"Dein Guthaben: {coins_str} 🪙")
    await interaction.response.send_message(embed=embed, view=RPGShopView(interaction.user.id))

class EnchantSelect(discord.ui.Select):
    def __init__(self, user_id: int, profile: dict):
        self.user_id = user_id
        options = []
        for key, ench in ENCHANTMENTS.items():
            curr_lvl = profile.get(ench["db_col"], 0)
            next_lvl = curr_lvl + 1
            if next_lvl in ench["levels"]:
                lvl_info = ench["levels"][next_lvl]
                cost_str = f"{lvl_info['cost']:,}".replace(",", ".")
                options.append(discord.SelectOption(
                    label=f"{ench['name']} Stufe {next_lvl} ({cost_str} 🪙)",
                    value=f"{key}_{next_lvl}",
                    description=lvl_info["desc"][:45],
                    emoji=ench["emoji"]
                ))
            else:
                options.append(discord.SelectOption(
                    label=f"{ench['name']} (MAXIMAL)",
                    value=f"{key}_max",
                    description="Bereits voll verzaubert!",
                    emoji=ench["emoji"]
                ))
        super().__init__(placeholder="Wähle eine Verzauberung aus...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("Öffne dein eigenes Menü!", ephemeral=True)

        val = self.values[0]
        if val.endswith("_max"):
            return await interaction.response.send_message("⭐ Diese Verzauberung ist bereits auf Maximalstufe!", ephemeral=True)

        ench_key, target_lvl_str = val.rsplit("_", 1)
        target_lvl = int(target_lvl_str)
        ench = ENCHANTMENTS[ench_key]
        lvl_info = ench["levels"][target_lvl]

        profile = await get_profile(self.user_id)
        if profile["coins"] < lvl_info["cost"]:
            cost_str = f"{lvl_info['cost']:,}".replace(",", ".")
            return await interaction.response.send_message(f"❌ Zu wenig Münzen! Kostet **{cost_str} 🪙**.", ephemeral=True)

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(f"UPDATE user_profiles SET coins = coins - ?, {ench['db_col']} = ? WHERE user_id = ?", (lvl_info["cost"], target_lvl, self.user_id))
            await db.commit()

        await interaction.response.send_message(
            f"🔮 Deine Rute wurde erfolgreich mit {ench['emoji']} **{ench['name']} Stufe {target_lvl}** verzaubert!\n*{lvl_info['desc']}*",
            ephemeral=True
        )

class EnchantView(discord.ui.View):
    def __init__(self, user_id: int, profile: dict):
        super().__init__(timeout=90.0)
        self.add_item(EnchantSelect(user_id, profile))

@bot.tree.command(name="verzaubern", description="Besuche den uralten Verzaubermeister für deine Angel.")
async def enchant(interaction: discord.Interaction):
    profile = await get_profile(interaction.user.id)
    embed = discord.Embed(
        title="🧙‍♂️ Der Verzaubermeister",
        description="Verleihe deiner Angelrute arkane Kräfte gegen Goldmünzen!\n\n"
                    "✨ **Glück des Meeres (I–III):** Erhöht Seltenheitschancen\n"
                    "🪱 **Köder-Sparer (I–II):** Spart Köder beim Auswerfen\n"
                    "🏴‍☠️ **Schatzsucher (I):** Zieht Schatztruhen mit Münzen an Land\n"
                    "⚖️ **Giganten-Köder (I–III):** Verleiht Fischen bis zu +100% Kampfgewicht & Wert\n"
                    "🪞 **Doppel-Haken (I–II):** Bis zu 40% Chance auf zwei Fische gleichzeitig\n"
                    "🌊 **Neptuns Segen (I):** Verbannt alten Müll komplett von deinem Haken\n"
                    "⚡ **Blitz-Reflexe (I–II):** Senkt den Angel-Cooldown auf 6s bzw. 3s!",
        color=discord.Color.purple()
    )
    coins_str = f"{profile['coins']:,}".replace(",", ".")
    embed.add_field(name="Dein Gold", value=f"{coins_str} 🪙", inline=False)
    view = EnchantView(interaction.user.id, profile)
    await interaction.response.send_message(embed=embed, view=view)


# ==========================================
# 10. BOT STARTEN
# ==========================================
# Setze hier deinen echten Bot-Token aus dem Discord Developer Portal ein:
bot.run(os.environ["DISCORD_TOKEN"])
