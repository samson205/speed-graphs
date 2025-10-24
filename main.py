import argparse
import os
import re
from datetime import date
from typing import Union

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from pdf_generator import PDFGenerator


class FileInfo:
    """Класс для хранения информации, извлеченной из файла"""
    all_tests = None
    mode = None
    total_blocks = None
    complete = None

    def __init__(self, all_tests: list, mode: str,
                 total_blocks: int, complete: bool):
        self.all_tests = all_tests
        self.mode = mode
        self.total_blocks = total_blocks
        self.complete = complete


def read_file(file_name: str) -> Union[FileInfo, None]:
    try:
        with open(file_name, 'r', encoding="utf-8") as file:
            lines = file.readlines()
    except FileNotFoundError:
        print("Файл не найден!")
        return None

    all_tests = []
    current = None

    mode_string = lines[0].strip().split()
    mode = mode_string[5]
    blocks = lines[1].strip()
    complete = False
    total_blocks_split = blocks.split()
    total_blocks = int(total_blocks_split[4]) - int(total_blocks_split[2])

    for line in lines[2:]:
        line = line.strip()
        if not line:
            continue

        if ":" in line:
            name, data_part = line.split(":", 1)
            if "with" in name:
                name = f"Запись ({name.split("with", 1)[-1].strip()})"
            new_data = re.sub(r'\x08', "END", data_part)
            data = new_data.split("END")
            current = {
                'name': name,
                'data': [],
                'total_blocks': total_blocks
            }

            for x in data:
                x = x.strip()
                if not x:
                    continue

                res = data_processed(x)
                if res is not None:
                    current['data'].append(res)
        else:
            if 'completed' in line:
                complete = True

        if current:
            all_tests.append(current)
            current = None

    if 'completed' in lines[-1]:
        return FileInfo(all_tests, mode, total_blocks, complete)

    return FileInfo([], mode, total_blocks, complete)


def data_processed(data: str) -> Union[dict, None]:
    pattern = r'(\d+\.?\d*)%\s+done,\s+((\d+):)?(\d+):(\d+)\s+elapsed.*?\((\d+)/(\d+)/(\d+)\s+errors\)'

    match = re.search(pattern, data)
    if match:
        percent = float(match.group(1))
        hours = int(match.group(3)) if match.group(3) else 0
        minutes = int(match.group(4))
        seconds = int(match.group(5))

        total_time = hours * 3600 + minutes * 60 + seconds

        return {
            'percent': percent,
            'total_time': total_time,
            'hours': hours,
            'minutes': minutes,
            'seconds': seconds
        }

    return None


def calculate_speed(test: dict) -> pd.DataFrame:
    data = test['data']

    df = pd.DataFrame(data)
    df['total_time'] -= df['total_time'].iloc[0]
    df['blocks_processed'] = test['total_blocks'] * (df['percent'] / 100)
    df['blocks_delta'] = df['blocks_processed'].diff()

    df = df[df['blocks_delta'] > 0]
    df['time_delta'] = df['total_time'].diff()
    df = df[df['time_delta'] > 0]

    b_per_sec = (df['blocks_delta'] * 1024) / df['time_delta']
    if b_per_sec.mean() >= 1024 * 1024:
        df['speed'] = b_per_sec / 1024 / 1024
        df['speed_dim'] = "МБ/с"
    elif b_per_sec.mean() >= 1024:
        df['speed'] = b_per_sec / 1024
        df['speed_dim'] = "кБ/с"
    else:
        df['speed'] = b_per_sec / 1024
        df['speed_dim'] = "байт/с"
    # df['kb_per_sec'] = df['b_per_sec'] / 1024
    # df['mb_per_sec'] = df['kb_per_sec'] / 1024

    df['test_name'] = test['name']

    return df


def plots(df_tests: list) -> None:
    if not os.path.exists("temp"):
        os.mkdir("temp")

    for i, current_test in enumerate(df_tests):
        fig1, ax1 = plt.subplots(figsize=(18, 10))
        new_x = np.linspace(0, current_test['total_time'].iloc[-1], 1500)
        new_y = np.interp(new_x, current_test['total_time'], current_test['speed'])
        ax1.plot(new_x, new_y)
        ax1.set_title(current_test['test_name'].iloc[0] +
                      " (зависимость скорости от времени)", fontsize=20)
        ax1.set_xlabel('Время, сек', fontsize=18)
        ax1.set_ylabel(f"Скорость, {current_test['speed_dim'].iloc[0]}", fontsize=18)
        ax1.grid(which='minor', color='0.85')
        ax1.minorticks_on()
        ax1.grid(which='major', color='0.5')
        ax1.tick_params(axis='both', which='major', labelsize=16)
        ax1.set_ylim(ymin=0)
        fig1.savefig(f"temp/test{i + 1}.png")

        fig2, ax2 = plt.subplots(figsize=(18, 10))
        new_x = np.linspace(0, current_test['percent'].iloc[-1], 1500)
        new_y = np.interp(new_x, current_test['percent'], current_test['speed'])
        ax2.plot(new_x, new_y)
        ax2.set_title(current_test['test_name'].iloc[0] +
                      " (зависимость скорости от объема)", fontsize=20)
        ax2.set_xlabel('Объем накопителя в %', fontsize=18)
        ax2.set_ylabel(f"Скорость, {current_test['speed_dim'].iloc[0]}", fontsize=18)
        ax2.grid(which='minor', color='0.85')
        ax2.minorticks_on()
        ax2.grid(which='major', color='0.5')
        ax2.ticklabel_format(style='plain')
        ax2.tick_params(axis='both', which='major', labelsize=16)
        ax2.set_ylim(ymin=0)
        fig2.savefig(f"temp/test{i + 1}_percent.png")

        plt.close("all")


def delete_images(folder_path: str = "temp") -> None:
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception:
            print(f"Ошибка при удалении файла {file_path}")


def mean_speed(df_tests: list) -> tuple[float, float]:
    all_read_speeds, all_write_speeds = [], []
    for i in range(len(df_tests)):
        current_test = df_tests[i]
        if "Запись" in current_test['test_name'].iloc[-1]:
            all_read_speeds.extend(current_test['speed'])
            continue
        all_write_speeds.extend(current_test['speed'])
    return round(pd.Series(all_write_speeds).mean(), 1), round(pd.Series(all_read_speeds).mean(), 1)


def min_speed(df_tests: list) -> tuple[float, float]:
    all_read_speeds, all_write_speeds = [], []
    for i in range(len(df_tests)):
        current_test = df_tests[i]
        if "Запись" in current_test['test_name'].iloc[-1]:
            all_read_speeds.extend(current_test['speed'])
            continue
        all_write_speeds.extend(current_test['speed'])
    return round(pd.Series(all_write_speeds).min(), 1), round(pd.Series(all_read_speeds).min(), 1)


def max_speed(df_tests: list) -> tuple[float, float]:
    all_read_speeds, all_write_speeds = [], []
    for i in range(len(df_tests)):
        current_test = df_tests[i]
        if "Запись" in current_test['test_name'].iloc[-1]:
            all_read_speeds.extend(current_test['speed'])
            continue
        all_write_speeds.extend(current_test['speed'])
    return round(pd.Series(all_write_speeds).max(), 1), round(pd.Series(all_read_speeds).max(), 1)


def mean_cycle_time(df_tests: list) -> str:
    all_time = [df_tests[i]['total_time'].iloc[-1] for i in range(len(df_tests))]
    mean_time = round(sum(all_time) / len(all_time))
    spread = round(((max(all_time) - min(all_time)) / mean_time) * 100, 2)
    return f"{mean_time // 3600}:{(mean_time % 3600) // 60}:{mean_time % 60}\n±{spread}%"


def format_blocks(blocks: int) -> str:
    size_kb = blocks

    if size_kb >= 1024 * 1024 * 1024:
        return f"{size_kb / 1024 / 1024 / 1024:.2f} ТБ"
    elif size_kb >= 1024 * 1024:
        return f"{size_kb / 1024 / 1024:.2f} ГБ"
    elif size_kb >= 1024:
        return f"{size_kb / 1024:.2f} МБ"
    return f"{size_kb} кБ"


def create_pdf(all_tests: FileInfo, file_name: str, output_dir: str = None) -> bool:
    if all_tests is None:
        return False

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{os.path.splitext(file_name)[0]}.pdf")

    else:
        output_path = f"{os.path.splitext(file_name)[0]}.pdf"

    tests, name, blocks, complete = (all_tests.all_tests, all_tests.mode,
                                     all_tests.total_blocks, all_tests.complete)
    if tests:
        df_tests = [calculate_speed(tests[i]) for i in range(len(tests))]
        plots(df_tests)
        generator = PDFGenerator(output_path)
        generator.add_title()
        time_string = (f"{df_tests[-1]['hours'].iloc[-1]}:" +
                       f"{df_tests[-1]['minutes'].iloc[-1]}:{df_tests[-1]['seconds'].iloc[-1]}")
        max_write, max_read = max_speed(df_tests)
        min_write, min_read = min_speed(df_tests)
        mean_write, mean_read = mean_speed(df_tests)
        mean_time = mean_cycle_time(df_tests)
        dim_r, dim_w = df_tests[1]['speed_dim'].iloc[0], df_tests[0]['speed_dim'].iloc[0]
        generator.add_table([
            ["Параметр", "Чтение", "Запись"],
            ["Название исходного файла", file_name],
            ["Дата генерации отчета", date.today().strftime("%d/%m/%Y")],
            ["Объем накопителя", f"{blocks:,} блоков\n{format_blocks(blocks)}"],
            ["Режим тестирования", name.capitalize()],
            ["Результат тестирования", "Пройдено"],
            ["Общее время тестирования", time_string],
            ["Количество проходов чтения\nи записи", len(tests)],
            ["Среднее время одного цикла\nчтения и записи", mean_time],
            ["Средняя скорость чтения и записи", f"{mean_read} {dim_r}", f"{mean_write} {dim_w}"],
            ["Минимальная скорость чтения\nи записи", f"{min_read} {dim_r}", f"{min_write} {dim_w}"],
            ["Максимальная скорость чтения\nи записи", f"{max_read} {dim_r}", f"{max_write} {dim_w}"]
        ])
        generator.add_page_break()

        tests_table = [
            ["Номер\nтеста", "Тип теста", "Время\nтестирования", "Средняя\nскорость",
             "Минимальная\nскорость", "Максимальная\nскорость"]
        ]
        for i in range(len(tests)):
            current_test = df_tests[i]
            speed_dim = current_test['speed_dim'].iloc[-1]
            total_time = current_test['total_time'].iloc[-1]
            time_string = f"{total_time // 3600}:{(total_time % 3600) // 60}:{total_time % 60}"
            tests_table.append(
                [i + 1, current_test['test_name'].iloc[-1], time_string,
                 f"{round(current_test['speed'].mean(), 1)} {speed_dim}",
                 f"{round(current_test['speed'].min(), 1)} {speed_dim}",
                 f"{round(current_test['speed'].max(), 1)} {speed_dim}"]
            )
        generator.add_table(tests_table, style="tests_table")

        for i in range(len(tests)):
            generator.add_image(f"temp/test{i + 1}.png")
            generator.add_image(f"temp/test{i + 1}_percent.png")
        generator.generate()
        delete_images()

    else:
        generator = PDFGenerator(output_path)
        generator.add_title()
        generator.add_table([
            ["Параметр", "Чтение", "Запись"],
            ["Название исходного файла", file_name],
            ["Дата генерации отчета", date.today().strftime("%d/%m/%Y")],
            ["Объем накопителя", f"{blocks} блоков\n{format_blocks(blocks)}"],
            ["Режим тестирования", name.capitalize()],
            ["Результат тестирования", "Провалено"],
            ["Общее время тестирования", "-"],
            ["Количество проходов чтения\nи записи", "-"],
            ["Среднее время одного цикла\nчтения и записи", "-"],
            ["Средняя скорость чтения и записи", "-"],
            ["Минимальная скорость чтения\nи записи", "-"],
            ["Максимальная скорость чтения\nи записи", "-"]
        ])

        generator.generate()

    return True


def process_file(file_path: str, output_dir: str = None) -> bool:
    tests_file = read_file(file_path)
    if tests_file is None:
        return False

    return create_pdf(tests_file, os.path.basename(file_path), output_dir)


def process_directory(directory: str, output_dir: str = None) -> None:
    if not os.path.exists(directory):
        print(f"Каталог {directory} не существует")
        return None

    for file in os.listdir(directory):
        if file.endswith(".bbl") or file.endswith(".log"):
            file_path = os.path.join(directory, file)
            if process_file(file_path, output_dir):
                print(f"Файл: {file_path}")
                print("Отчет успешно сгенерирован\n")

    return None


def main() -> None:
    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-f", "--file", type=str, help="Файл для обработки (.bbl или .log)")
    group.add_argument("-d", "--directory", type=str, help="Каталог с файлами для обработки")

    parser.add_argument("-o", "--output", type=str, help="Каталог для сохранения отчетов")

    args = parser.parse_args()

    if args.file:
        if process_file(args.file, output_dir=args.output):
            print(f"Файл: {args.file}")
            print("Отчет успешно сгенерирован\n")
            return

    elif args.directory:
        process_directory(args.directory, output_dir=args.output)
        return

    if process_file(input("Введите путь до файла: ")):
        print("Отчет успешно сгенерирован")


if __name__ == "__main__":
    main()
