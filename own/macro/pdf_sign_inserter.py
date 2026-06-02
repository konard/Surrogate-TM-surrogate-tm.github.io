#!/usr/bin/env python3
"""
Insert signature PDFs from the `sign` folder into PDF documents from the `in`
folder, and save results to the `out` folder.

Dependencies:
    pip install pypdf
"""

import argparse
import math
import sys
from copy import deepcopy
from pathlib import Path

try:
    from pypdf import PageObject, PdfReader, PdfWriter, Transformation
    from pypdf.generic import RectangleObject
except ImportError:
    sys.exit("Error: pypdf not installed. Run: pip install pypdf")

A4_WIDTH_PT = 595.28
A4_HEIGHT_PT = 841.89


def ensure_dirs(*dirs: Path) -> None:
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)


def check_non_empty(folder: Path, label: str) -> None:
    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        sys.exit(
            f"Warning: The '{label}' folder ({folder}) contains no PDF files.\n"
            f"Please add PDF documents to '{folder}' and run the script again."
        )


def nearest_a4_multiple(size_pt: float, a4_dim: float) -> float:
    return max(math.ceil(size_pt / a4_dim), 1) * a4_dim


def is_a4_multiple(width: float, height: float, tol: float = 1.0) -> bool:
    w_mult = width / A4_WIDTH_PT
    h_mult = height / A4_HEIGHT_PT
    return (
        abs(w_mult - round(w_mult)) < tol / A4_WIDTH_PT
        and abs(h_mult - round(h_mult)) < tol / A4_HEIGHT_PT
    )


def adjusted_page_size(width: float, height: float) -> tuple[float, float]:
    if is_a4_multiple(width, height):
        return width, height
    return (
        nearest_a4_multiple(width, A4_WIDTH_PT),
        nearest_a4_multiple(height, A4_HEIGHT_PT),
    )


def adjust_page_size(page: PageObject) -> PageObject:
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    new_width, new_height = adjusted_page_size(width, height)

    if new_width == width and new_height == height:
        return page

    adjusted = PageObject.create_blank_page(width=new_width, height=new_height)
    adjusted.merge_page(page)
    return adjusted


def load_sign_pages(sign_paths: list[Path]) -> list[PageObject]:
    sign_pages: list[PageObject] = []

    for sign_path in sign_paths:
        reader = PdfReader(str(sign_path))
        if not reader.pages:
            print(f"  Warning: sign document '{sign_path.name}' has no pages - skipping.")
            continue
        sign_pages.append(deepcopy(reader.pages[0]))

    return sign_pages


def get_sign_rect_on_page(sign_page: PageObject) -> RectangleObject:
    return sign_page.mediabox


def insert_sign_into_page(out_page: PageObject, sign_page: PageObject) -> None:
    sign_copy = deepcopy(sign_page)
    sign_rect = get_sign_rect_on_page(sign_copy)

    page_width = float(out_page.mediabox.width)
    page_height = float(out_page.mediabox.height)
    sign_width = float(sign_rect.width)
    sign_height = float(sign_rect.height)

    scale = min(1.0, page_width / sign_width, page_height / sign_height)
    transform = Transformation().scale(scale).translate(
        tx=-float(sign_rect.left) * scale,
        ty=-float(sign_rect.bottom) * scale,
    )
    out_page.merge_transformed_page(sign_copy, transform, over=True)


def process_pdf(in_path: Path, sign_pages: list[PageObject], out_path: Path) -> None:
    print(f"  Processing: {in_path.name}")
    reader = PdfReader(str(in_path))
    writer = PdfWriter()
    n_signs = len(sign_pages)

    for page_idx, original_page in enumerate(reader.pages):
        page = adjust_page_size(deepcopy(original_page))
        insert_sign_into_page(page, sign_pages[page_idx % n_signs])
        writer.add_page(page)

    with out_path.open("wb") as out_file:
        writer.write(out_file)

    print(f"    Saved: {out_path.name}")


def main() -> None:
    script_dir = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description=(
            "Insert signature PDFs from 'sign/' into PDFs in 'in/',\n"
            "saving results to 'out'.\n\n"
            "Requires: pip install pypdf"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--in-dir",
        default=str(script_dir / "in"),
        help="Folder with input PDFs (default: in/ next to script)",
    )
    parser.add_argument(
        "--sign-dir",
        default=str(script_dir / "sign"),
        help="Folder with sign PDFs (default: sign/ next to script)",
    )
    parser.add_argument(
        "--out-dir",
        default=str(script_dir / "out"),
        help="Output folder (default: out/ next to script)",
    )
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    sign_dir = Path(args.sign_dir)
    out_dir = Path(args.out_dir)

    ensure_dirs(in_dir, sign_dir, out_dir)
    check_non_empty(in_dir, "in")
    check_non_empty(sign_dir, "sign")

    sign_paths = sorted(sign_dir.glob("*.pdf"))
    print(f"Found {len(sign_paths)} sign document(s): {[p.name for p in sign_paths]}")
    sign_pages = load_sign_pages(sign_paths)

    if not sign_pages:
        sys.exit(
            "Warning: No valid sign documents found in the 'sign' folder.\n"
            "Please add single-page PDF documents with images to the 'sign' folder."
        )

    in_paths = sorted(in_dir.glob("*.pdf"))
    print(f"\nFound {len(in_paths)} input document(s): {[p.name for p in in_paths]}")
    print()

    for in_path in in_paths:
        out_path = out_dir / in_path.name
        try:
            process_pdf(in_path, sign_pages, out_path)
        except Exception as exc:
            print(f"  Error processing '{in_path.name}': {exc}")

    print("\nDone.")


if __name__ == "__main__":
    main()
