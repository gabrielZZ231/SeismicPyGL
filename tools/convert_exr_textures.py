#!/usr/bin/env python3
"""
Ferramenta de pré-processamento de texturas PBR para o SeismicPyGL:
- Converte arquivos .exr (OpenEXR) para .png de 8 bits usando OpenEXR / OpenCV.
- Redimensiona texturas 4K para 2048x2048 por padrão (cv2.INTER_AREA) para performance fluida e 60 FPS.
- Suporta flag --full-4k para manter a resolução nativa original.
"""

import os
import sys
import argparse
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import OpenEXR
    import Imath
except ImportError:
    OpenEXR = None
    Imath = None


def read_exr_file(filepath: str) -> np.ndarray:
    """Lê arquivo .exr usando cv2.imread ou OpenEXR nativo."""
    if cv2 is not None:
        img = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
        if img is not None:
            if len(img.shape) == 3 and img.shape[2] == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            return img

    if OpenEXR is not None:
        exr = OpenEXR.InputFile(filepath)
        dw = exr.header()["dataWindow"]
        width = dw.max.x - dw.min.x + 1
        height = dw.max.y - dw.min.y + 1
        channels = exr.header()["channels"].keys()
        pt = Imath.PixelType(Imath.PixelType.FLOAT)

        if "R" in channels and "G" in channels and "B" in channels:
            r = np.frombuffer(exr.channel("R", pt), dtype=np.float32).reshape((height, width))
            g = np.frombuffer(exr.channel("G", pt), dtype=np.float32).reshape((height, width))
            b = np.frombuffer(exr.channel("B", pt), dtype=np.float32).reshape((height, width))
            img = np.stack([r, g, b], axis=-1)
        elif "Y" in channels:
            img = np.frombuffer(exr.channel("Y", pt), dtype=np.float32).reshape((height, width))
        else:
            c = list(channels)[0]
            img = np.frombuffer(exr.channel(c, pt), dtype=np.float32).reshape((height, width))
        return img

    raise RuntimeError(f"Não foi possível ler {filepath}. Instale opencv-python ou openexr.")


def convert_exr_textures(root_dir: str = "assets/textures/pbr", target_size: int = 2048, full_4k: bool = False):
    """Percorre root_dir e converte todos os .exr em .png."""
    if not os.path.exists(root_dir):
        print(f"[Erro] Diretório \"{root_dir}\" não encontrado!")
        return

    exr_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.lower().endswith(".exr"):
                exr_files.append(os.path.join(dirpath, f))

    print(f"Encontrados {len(exr_files)} arquivos .exr em \"{root_dir}\".")
    resolution_label = "Nativa 4K (4096)" if full_4k else f"{target_size}x{target_size}"
    print(f"Modo de resolução: {resolution_label}\n")

    for i, exr_path in enumerate(exr_files, 1):
        png_path = os.path.splitext(exr_path)[0] + ".png"
        basename = os.path.basename(exr_path)
        print(f"[{i}/{len(exr_files)}] Convertendo {basename}...")

        try:
            img = read_exr_file(exr_path)

            if img.dtype in (np.float32, np.float64, np.float16):
                img_8bit = np.clip(img * 255.0, 0.0, 255.0).astype(np.uint8)
            else:
                img_8bit = img.astype(np.uint8)

            if not full_4k:
                h, w = img_8bit.shape[:2]
                if w != target_size or h != target_size:
                    if cv2 is not None:
                        img_8bit = cv2.resize(img_8bit, (target_size, target_size), interpolation=cv2.INTER_AREA)
                    else:
                        from PIL import Image
                        pil_img = Image.fromarray(img_8bit)
                        pil_img = pil_img.resize((target_size, target_size), Image.Resampling.LANCZOS)
                        img_8bit = np.array(pil_img)

            if cv2 is not None:
                if len(img_8bit.shape) == 3 and img_8bit.shape[2] == 3:
                    save_img = cv2.cvtColor(img_8bit, cv2.COLOR_RGB2BGR)
                else:
                    save_img = img_8bit
                cv2.imwrite(png_path, save_img)
            else:
                from PIL import Image
                Image.fromarray(img_8bit).save(png_path)

            print(f"       Salvo: {png_path} ({img_8bit.shape})")
        except Exception as e:
            print(f"       [Falha ao converter {basename}]: {e}")

    print("\nProcessamento concluído com sucesso!")


def main():
    parser = argparse.ArgumentParser(description="Conversor de texturas EXR para PNG otimizadas para o SeismicPyGL.")
    parser.add_argument("--dir", default="assets/textures/pbr", help="Diretório raiz com os materiais PBR")
    parser.add_argument("--size", type=int, default=2048, help="Resolução alvo em pixels (padrão: 2048)")
    parser.add_argument("--full-4k", action="store_true", help="Mantém resolução 4K original sem redimensionar")
    args = parser.parse_args()

    convert_exr_textures(root_dir=args.dir, target_size=args.size, full_4k=args.full_4k)


if __name__ == "__main__":
    main()
