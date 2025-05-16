import os
import json
import subprocess
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters, ContextTypes
import logging
from decimal import Decimal
from base58 import b58decode

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Keypair directory
#KEYPAIR_DIR = Path("/app/keypairs")
KEYPAIR_DIR = Path("keypairs")
KEYPAIR_DIR.mkdir(exist_ok=True)
os.chmod(KEYPAIR_DIR, 0o700)

# Bot's keypair and address
#BOT_KEYPAIR = Path("/app/bot_keypair/ErEBS6qJqRBmF8Brot77LyrGnGJgRijX1LudBjwN6EAs.json")
BOT_KEYPAIR = Path("bot_keypair/ErEBS6qJqRBmF8Brot77LyrGnGJgRijX1LudBjwN6EAs.json")
BOT_ADDRESS = "ErEBS6qJqRBmF8Brot77LyrGnGJgRijX1LudBjwN6EAs"

# Solana CLI commands
SOLANA_CLI = "solana"
SOLANA_KEYGEN = "solana-keygen"
SPL_TOKEN_CLI = "spl-token"

# Token mint addresses
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
ERBS_USDC_MINT = "CNfuSdLitgsFyRKhpaAVA2WM9q8wbEgvksJRvwgVoak3"

# Conversation states
ASK_FOR_PUBKEY = 0

def get_public_key(keypair_path: Path) -> str:
    """Extract public key from keypair file."""
    result = subprocess.run(
        [SOLANA_KEYGEN, "pubkey", str(keypair_path)],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()

def get_balances(keypair_path: Path) -> dict:
    """Fetch SOL, USDC, and ERBS_USDC balances."""
    public_key = get_public_key(keypair_path)
    sol_result = subprocess.run(
        [SOLANA_CLI, "balance", public_key],
        capture_output=True,
        text=True,
        check=True
    )
    sol_balance = float(sol_result.stdout.strip().split()[0])

    usdc_balance = 0.0
    erbs_usdc_balance = 0.0
    cnf_account_exists = False
    spl_result = subprocess.run(
        [SPL_TOKEN_CLI, "accounts", "--owner", str(keypair_path)],
        capture_output=True,
        text=True,
        check=True
    )
    for line in spl_result.stdout.splitlines():
        if USDC_MINT in line:
            usdc_balance = float(line.split()[-1])
        if ERBS_USDC_MINT in line:
            erbs_usdc_balance = float(line.split()[-1])
            cnf_account_exists = True

    return {
        "sol": sol_balance,
        "usdc": usdc_balance,
        "erbs_usdc": erbs_usdc_balance,
        "cnf_account_exists": cnf_account_exists
    }

def create_main_keyboard() -> InlineKeyboardMarkup:
    """Create main keyboard with updated button names."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Create CNf Account", callback_data="create_cnf")],
        [InlineKeyboardButton("Configure Confidential", callback_data="configure_conf")],
        [InlineKeyboardButton("Check Balance", callback_data="check_balance")],
        [InlineKeyboardButton("Withdraw Confidential Tokens", callback_data="withdraw_conf")],
        [InlineKeyboardButton("Confidential Transfer confUSD", callback_data="transfer_conf")],
        [InlineKeyboardButton("Redeem confUSD for USD", callback_data="redeem_conf")],
        [InlineKeyboardButton("Send USDC (Get cnfUSD)", callback_data="send_usdc")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user_id = update.effective_user.id
    keypair_path = KEYPAIR_DIR / f"{user_id}.json"

    if not keypair_path.exists():
        subprocess.run(
            [SOLANA_KEYGEN, "new", "--no-bip39-passphrase", "--silent", "--outfile", str(keypair_path)],
            check=True
        )
        os.chmod(keypair_path, 0o600)

        with open(keypair_path, "r") as f:
            private_key = json.dumps(json.load(f))

        public_key = get_public_key(keypair_path)
        await update.message.reply_text(
            f"New wallet created!\nPublic Key: {public_key}\nPrivate Key: {private_key}\n\n"
            "⚠️ Save your private key and delete this message!",
            reply_markup=create_main_keyboard()
        )
    else:
        public_key = get_public_key(keypair_path)
        await update.message.reply_text(
            f"Welcome back!\nPublic Key: {public_key}",
            reply_markup=create_main_keyboard()
        )

async def check_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle balance check."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    keypair_path = KEYPAIR_DIR / f"{user_id}.json"

    if not keypair_path.exists():
        await query.message.reply_text("No wallet found. Use /start.")
        return

    public_key = get_public_key(keypair_path)
    balances = get_balances(keypair_path)
    cnf_status = "exists" if balances["cnf_account_exists"] else "does not exist"
    await query.message.reply_text(
        f"Public Key: {public_key}\n"
        f"Balances:\n- SOL: {balances['sol']}\n- USDC: {balances['usdc']}\n- ERBS_USDC: {balances['erbs_usdc']}\n"
        f"CNf Account: {cnf_status}",
        reply_markup=create_main_keyboard()
    )

async def send_usdc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send USDC and receive cnfUSD with step-by-step updates."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    keypair_path = KEYPAIR_DIR / f"{user_id}.json"

    if not keypair_path.exists():
        await query.message.reply_text("No wallet found. Use /start.")
        return

    balances = get_balances(keypair_path)
    if balances["sol"] < 0.03 or balances["usdc"] < 0.43:
        await query.message.reply_text("Need >0.03 SOL and >0.43 USDC to proceed.")
        return

    try:
        # User sends USDC to bot
        await query.message.reply_text("⚡ Sending 0.42 USDC to get your cnfUSD...")
        result = subprocess.run(
            [SPL_TOKEN_CLI, "transfer", "--owner", str(keypair_path), USDC_MINT, "0.42", BOT_ADDRESS],
            capture_output=True,
            text=True,
            check=True
        )
        tx_signature = result.stdout.strip().split()[-1]
        await query.message.reply_text(f"✅ Sent 0.42 USDC!\nTx: `{tx_signature}`")

        # Bot sends cnfUSD to user
        await query.message.reply_text("⚡ Bot’s sending 0.42 cnfUSD your way...")
        user_public_key = get_public_key(keypair_path)
        bot_result = subprocess.run(
            [SPL_TOKEN_CLI, "transfer", "--owner", str(BOT_KEYPAIR), ERBS_USDC_MINT, "0.42", user_public_key, "--confidential"],
            capture_output=True,
            text=True,
            check=True
        )
        bot_tx_signature = bot_result.stdout.strip().split()[-1]
        await query.message.reply_text(f"✅ Got 0.42 cnfUSD (private)!\nTx: `{bot_tx_signature}`")

        # Bot applies pending balance
        await query.message.reply_text("⚡ Bot’s locking in its balance...")
        bot_apply_result = subprocess.run(
            [SPL_TOKEN_CLI, "apply-pending-balance", ERBS_USDC_MINT, "--owner", str(BOT_KEYPAIR)],
            capture_output=True,
            text=True,
            check=True
        )
        bot_apply_signature = bot_apply_result.stdout.strip().split()[-1]
        await query.message.reply_text(f"✅ Bot’s balance set!\nTx: `{bot_apply_signature}`")

        # User applies pending balance
        await query.message.reply_text("⚡ Locking in your balance...")
        user_apply_result = subprocess.run(
            [SPL_TOKEN_CLI, "apply-pending-balance", ERBS_USDC_MINT, "--owner", str(keypair_path)],
            capture_output=True,
            text=True,
            check=True
        )
        user_apply_signature = user_apply_result.stdout.strip().split()[-1]
        await query.message.reply_text(f"✅ Your balance is ready!\nTx: `{user_apply_signature}`")

        # Final message
        await query.message.reply_text(
            "🎉 Hell yeah! You’ve got 0.42 cnfUSD (private USD). Cash it out anytime with:\n"
            "```\nspl-token withdraw-confidential-tokens CNfuSdLitgsFyRKhpaAVA2WM9q8wbEgvksJRvwgVoak3 0.42\n```",
            reply_markup=create_main_keyboard()
        )
    except subprocess.CalledProcessError as e:
        await query.message.reply_text(f"❌ Oops, something broke: {e.stderr}")

async def redeem_conf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Redeem confUSD for USDC with a 0.42% fee and step-by-step updates."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    keypair_path = KEYPAIR_DIR / f"{user_id}.json"

    if not keypair_path.exists():
        await query.message.reply_text("No wallet found. Use /start.")
        return

    balances = get_balances(keypair_path)
    if balances["sol"] < 0.03 or balances["erbs_usdc"] < 0.42:
        await query.message.reply_text("Need >0.03 SOL and >0.42 ERBS_USDC to redeem.")
        return

    try:
        # Step 1: User sends 0.42 ERBS_USDC to bot
        await query.message.reply_text("⚡ Sending 0.42 ERBS_USDC to bot...")
        result = subprocess.run(
            [SPL_TOKEN_CLI, "transfer", "--owner", str(keypair_path), ERBS_USDC_MINT, "0.42", BOT_ADDRESS],
            capture_output=True,
            text=True,
            check=True
        )
        tx_signature = result.stdout.strip().split()[-1]
        await query.message.reply_text(f"✅ Sent 0.42 ERBS_USDC!\nTx: `{tx_signature}`")

        # Step 2: Calculate the 0.42% fee and USDC amount
        redeem_amount = Decimal('0.42')
        fee_percent = Decimal('0.0042')  # 0.42%
        fee = redeem_amount * fee_percent
        usdc_to_send = redeem_amount - fee

        # Step 3: Bot sends adjusted USDC to user
        await query.message.reply_text(f"⚡ Bot’s sending {usdc_to_send:.6f} USDC (after 0.42% fee)...")
        user_public_key = get_public_key(keypair_path)
        bot_result = subprocess.run(
            [SPL_TOKEN_CLI, "transfer", "--owner", str(BOT_KEYPAIR), USDC_MINT, str(usdc_to_send), user_public_key],
            capture_output=True,
            text=True,
            check=True
        )
        bot_tx_signature = bot_result.stdout.strip().split()[-1]
        await query.message.reply_text(f"✅ Got {usdc_to_send:.6f} USDC!\nTx: `{bot_tx_signature}`")

        # Step 4: Final confirmation with fee details
        await query.message.reply_text(
            f"🎉 Sweet! You’ve swapped 0.42 ERBS_USDC for {usdc_to_send:.6f} USDC (fee: {fee:.6f}).",
            reply_markup=create_main_keyboard()
        )
    except subprocess.CalledProcessError as e:
        await query.message.reply_text(f"❌ Damn, error hit: {e.stderr}")

async def create_cnf_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create CNf account."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    keypair_path = KEYPAIR_DIR / f"{user_id}.json"

    if not keypair_path.exists():
        await query.message.reply_text("No wallet found. Use /start.")
        return

    balances = get_balances(keypair_path)
    if balances["sol"] < 0.03:
        await query.message.reply_text("Need >0.03 SOL to create CNf account.")
        return

    try:
        result = subprocess.run(
            [SPL_TOKEN_CLI, "create-account", "--owner", str(keypair_path), ERBS_USDC_MINT],
            capture_output=True,
            text=True,
            check=True
        )
        lines = result.stdout.strip().splitlines()
        tx_signature = lines[-1].split()[-1]
        token_account = lines[0].split()[-1]
        context.user_data["cnf_account"] = token_account
        await query.message.reply_text(
            f"✅ CNf account created: {token_account}\nTx: `{tx_signature}`",
            reply_markup=create_main_keyboard()
        )
    except subprocess.CalledProcessError as e:
        await query.message.reply_text(f"❌ Error: {e.stderr}")

async def configure_confidential(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Configure confidential transfers."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    keypair_path = KEYPAIR_DIR / f"{user_id}.json"

    if not keypair_path.exists():
        await query.message.reply_text("No wallet found. Use /start.")
        return

    balances = get_balances(keypair_path)
    if balances["sol"] < 0.03:
        await query.message.reply_text("Need >0.03 SOL to configure.")
        return

    try:
        result = subprocess.run(
            [SPL_TOKEN_CLI, "configure-confidential-transfer-account", "--owner", str(keypair_path), ERBS_USDC_MINT],
            capture_output=True,
            text=True,
            check=True
        )
        tx_signature = result.stdout.strip().split()[-1]
        await query.message.reply_text(
            f"✅ Confidential transfers ready!\nTx: `{tx_signature}`",
            reply_markup=create_main_keyboard()
        )
    except subprocess.CalledProcessError as e:
        await query.message.reply_text(f"❌ Error: {e.stderr}")

async def withdraw_confidential(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Withdraw confidential tokens."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    keypair_path = KEYPAIR_DIR / f"{user_id}.json"

    if not keypair_path.exists():
        await query.message.reply_text("No wallet found. Use /start.")
        return

    balances = get_balances(keypair_path)
    if balances["sol"] < 0.03:
        await query.message.reply_text("Need >0.03 SOL for fees.")
        return

    try:
        await query.message.reply_text("⚡ Withdrawing 0.4 confidential tokens...")
        result = subprocess.run(
            [SPL_TOKEN_CLI, "withdraw-confidential-tokens", ERBS_USDC_MINT, "0.4", "--owner", str(keypair_path)],
            capture_output=True,
            text=True,
            check=True
        )
        tx_signature = result.stdout.strip().split()[-1]
        await query.message.reply_text(
            f"✅ Withdrew 0.4 tokens!\nTx: `{tx_signature}`",
            reply_markup=create_main_keyboard()
        )
    except subprocess.CalledProcessError as e:
        await query.message.reply_text(f"❌ Error: {e.stderr}")

# New functions for confidential transfer
async def start_transfer_conf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the confidential transfer process by asking for the recipient's public key."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Please enter the recipient's Solana public key for the confidential transfer:")
    return ASK_FOR_PUBKEY

async def receive_pubkey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive and validate the public key, then perform the confidential transfer."""
    user_id = update.message.from_user.id
    keypair_path = KEYPAIR_DIR / f"{user_id}.json"
    pubkey = update.message.text.strip()

    # Validate Solana public key (44 characters, base58)
    try:
        b58decode(pubkey)
        if len(pubkey) != 44:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text("❌ Invalid public key. Please enter a valid Solana public key.")
        return ASK_FOR_PUBKEY

    # Check if user's wallet exists
    if not keypair_path.exists():
        await update.message.reply_text("No wallet found. Use /start.")
        return ConversationHandler.END

    # Check balances
    balances = get_balances(keypair_path)
    if balances["sol"] < 0.03 or balances["erbs_usdc"] < 0.42:
        await update.message.reply_text("Need >0.03 SOL and >0.42 ERBS_USDC to transfer.")
        return ConversationHandler.END

    try:
        # Perform confidential transfer
        await update.message.reply_text(f"⚡ Sending 0.42 confUSD to {pubkey}...")
        result = subprocess.run(
            [SPL_TOKEN_CLI, "transfer", "--owner", str(keypair_path), ERBS_USDC_MINT, "0.42", pubkey, "--confidential"],
            capture_output=True,
            text=True,
            check=True
        )
        tx_signature = result.stdout.strip().split()[-1]
        await update.message.reply_text(
            f"✅ Sent 0.42 confUSD to {pubkey}!\nTx: `{tx_signature}`",
            reply_markup=create_main_keyboard()
        )
    except subprocess.CalledProcessError as e:
        await update.message.reply_text(f"❌ Error during transfer: {e.stderr}")

    return ConversationHandler.END

def main() -> None:
    """Run the bot."""
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        token = "7651550366:AAEaqiGfl5a8hTuiz_hZFOiSLAyPlLmXWHw"
        #raise ValueError("TELEGRAM_TOKEN environment variable not set")
    application = Application.builder().token(token).build()
    
    # Conversation handler for confidential transfer
    transfer_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_transfer_conf, pattern="transfer_conf")],
        states={
            ASK_FOR_PUBKEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pubkey)],
        },
        fallbacks=[],
    )

    # Add handlers (keeping all original ones)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(check_balance, pattern="check_balance"))
    application.add_handler(CallbackQueryHandler(send_usdc, pattern="send_usdc"))
    application.add_handler(CallbackQueryHandler(create_cnf_account, pattern="create_cnf"))
    application.add_handler(CallbackQueryHandler(configure_confidential, pattern="configure_conf"))
    application.add_handler(CallbackQueryHandler(withdraw_confidential, pattern="withdraw_conf"))
    application.add_handler(transfer_conv_handler)  # Replaced the old transfer_conf handler
    application.add_handler(CallbackQueryHandler(redeem_conf, pattern="redeem_conf"))

    application.run_polling()

if __name__ == "__main__":
    main()