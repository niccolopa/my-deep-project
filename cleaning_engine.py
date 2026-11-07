import argparse
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime

# STRICT LOCK: Must match the locked markets defined in locks.md
LOCKED_MARKET = {"EEM"}

def setup_logger(log_dir: Path) -> logging.Logger:
    """Configures a logger to write to the specified directory with a timestamp."""
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_file = log_dir / f"cleaning_engine_{timestamp}.log"

    logger = logging.getLogger("CleaningEngine")
    logger.setLevel(logging.INFO)

    # File handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger


def load_raw_data_from_manifest(manifest_path: Path, logger: logging.Logger) -> dict[str, pd.DataFrame]:
    """
    Reads the download manifest, enforces market locks, and loads valid raw csvs into memory.
    Raises FileNotFoundError if the manifest or any expected data file is missing.
    """
    if not manifest_path.exists():
        err_msg = f"Manifest file not found: {manifest_path}"
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)

    logger.info(f"Reading manifest: {manifest_path}")
    manifest = pd.read_csv(manifest_path)
    manifest.columns = manifest.columns.str.strip().str.lower()

    raw_dataframes = {}

    for _, row in manifest.iterrows():
        symbol = row['symbol']
        status = str(row['status']).lower()

        # 1. check download status
        if status != 'ok':
            logger.info(f"Skipping {symbol}: Manifest status is '{status}'.")
            continue

        # 2. enforce fail-closed lock:
        # this must happen before any file reading attempt
        if symbol in LOCKED_MARKET:
            logger.warning(f"LOCK ENFORCED: Refusing to read data for {symbol}")
            continue

        # 3. verify file existence and load
        file_path = manifest_path.parent / f"{symbol}_daily_raw.csv"

        if not file_path.exists():
            err_msg = f"Data file listed as 'ok' in manifest but missing on disk: {file_path}"
            logger.error(err_msg)
            raise FileNotFoundError(err_msg)

        raw_dataframes[symbol] = pd.read_csv(file_path)

    logger.info(f"Ingestion complete. Successfully loaded {len(raw_dataframes)} assets into memory.")
    return raw_dataframes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Cleaning engine - phase 1 data ingestion')
    parser.add_argument(
        "manifest",
        type=str,
        help="explicit path to the manifest.csv of the target download session."
    )
    args = parser.parse_args()

    # setup logging
    log_directory = Path(r"C:\dev\personal_projects\my-deep-project\data\logs")
    logger = setup_logger(log_directory)

    # run the ingestion step
    try:
        data_dict = load_raw_data_from_manifest(Path(args.manifest), logger)
    except Exception as e:
        logger.critical(f'engine failure: {e}')
        raise