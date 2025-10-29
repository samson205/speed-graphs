import argparse
import os
import re
from datetime import date
from typing import Union, Tuple

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
    block_size = None

    def __init__(self, all_tests: list, mode: str,
                 total_blocks: int, complete: bool, block_size: int = 1):
        self.all_tests = all_tests
        self.mode = mode
        self.total_blocks = total_blocks
        self.complete = complete
        self.block_size = block_size


def get_block_size(file_name: str) -> int:
    filename_upper = file_name.upper()
    match = re.search(r'(\d+)T', filename_upper)
    if match:
        size = int(match.group(1))
        return 4 if size > 4 else 1

    return 1


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
    block_size = get_block_size(file_name)

    for line in lines[2:]:
        line = line.strip()
        if not line:
            continue

        if ":" in line and ("badblocks" not in line):
            name, data_part = line.split(":", 1)
            if "Testing" in name:
                name = f"Запись ({name.split('with', 1)[-1].strip()})"
            elif "Reading and comparing" in name:
                name = "Чтение и сравнение"
            elif "Reading" in name:
                name = "Чтение"

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
                elif res is None and x != "done":
                    if current:
                        all_tests.append(current)
                    return FileInfo(all_tests, mode, total_blocks, complete, block_size)
        else:
            if 'completed' in line:
                complete = True

        if current:
            all_tests.append(current)
            current = None

    return FileInfo(all_tests, mode, total_blocks, complete, block_size)


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


def calculate_speed(test: dict, block_size: int) -> pd.DataFrame:
    data = test['data']

    df = pd.DataFrame(data)
    df['total_time'] -= df['total_time'].iloc[0]
    df['blocks_processed'] = test['total_blocks'] * (df['percent'] / 100)
    df['blocks_delta'] = df['blocks_processed'].diff()

    df = df[df['blocks_delta'] > 0]
    df['time_delta'] = df['total_time'].diff()
    df = df[df['time_delta'] > 0]

    b_per_sec = (df['blocks_delta'] * 1024 * block_size) / df['time_delta']
    if b_per_sec.mean() >= 1024 * 1024:
        df['speed'] = b_per_sec / 1024 / 1024
        df['speed_dim'] = "МБ/с"
    elif b_per_sec.mean() >= 1024:
        df['speed'] = b_per_sec / 1024
        df['speed_dim'] = "кБ/с"
    else:
        df['speed'] = b_per_sec / 1024
        df['speed_dim'] = "байт/с"

    df['test_name'] = test['name']

    return df


def plots(df_tests: list, combined: bool = False) -> None:
    if not os.path.exists("temp"):
        os.mkdir("temp")

    if combined:
        combined_plots(df_tests)

    for i, current_test in enumerate(df_tests):
        if "Запись" in current_test['test_name'].iloc[0]:
            color = "firebrick"
        else:
            color = "#1f77b4"

        fig1, ax1 = plt.subplots(figsize=(18, 10))
        new_x = np.linspace(0, current_test['total_time'].iloc[-1], 1500)
        new_y = np.interp(new_x, current_test['total_time'], current_test['speed'])
        ax1.plot(new_x, new_y, color=color)
        ax1.set_title(current_test['test_name'].iloc[0], fontsize=22)
        ax1.set_xlabel('Время', fontsize=20)
        ax1.set_ylabel(f"Скорость, {current_test['speed_dim'].iloc[0]}", fontsize=20)
        ax1.grid(which='minor', color='0.85')
        ax1.minorticks_on()
        ax1.grid(which='major', color='0.5')
        ax1.tick_params(axis='both', which='major', labelsize=18)
        ax1.set_ylim(ymin=0)
        ax1.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: format_time(x)))
        fig1.savefig(f"temp/test{i + 1}.png")

        fig2, ax2 = plt.subplots(figsize=(18, 10))
        new_x = np.linspace(0, current_test['percent'].iloc[-1], 1500)
        new_y = np.interp(new_x, current_test['percent'], current_test['speed'])
        ax2.plot(new_x, new_y, color=color)
        ax2.set_title(current_test['test_name'].iloc[0], fontsize=22)
        ax2.set_xlabel('Объем накопителя в %', fontsize=20)
        ax2.set_ylabel(f"Скорость, {current_test['speed_dim'].iloc[0]}", fontsize=20)
        ax2.grid(which='minor', color='0.85')
        ax2.minorticks_on()
        ax2.grid(which='major', color='0.5')
        ax2.ticklabel_format(style='plain')
        ax2.tick_params(axis='both', which='major', labelsize=18)
        ax2.set_ylim(ymin=0)
        fig2.savefig(f"temp/test{i + 1}_percent.png")

        plt.close("all")


def combined_plots(df_tests: list) -> None:
    test_cycles = []
    i = 0

    while i < len(df_tests) - 1:
        current_test = df_tests[i]
        current_name = current_test['test_name'].iloc[0]
        is_write = "Запись" in current_name

        if is_write:
            next_test = df_tests[i + 1]
            next_name = next_test['test_name'].iloc[0]
            next_is_write = "Запись" in next_name

            if not next_is_write:
                test_cycles.append([current_test, next_test])  # Запись, чтение
                i += 2
                continue

        else:
            next_test = df_tests[i + 1]
            next_name = next_test['test_name'].iloc[0]
            next_is_write = "Запись" in next_name

            if next_is_write:
                test_cycles.append([next_test, current_test])  # Запись, чтение
                i += 2
                continue

        i += 1

    colors = ['#1f77b4', 'firebrick']
    labels = ['Чтение', 'Запись']

    for i, cycle in enumerate(test_cycles):
        write_test, read_test = cycle

        write_time = write_test['total_time']
        write_speed = write_test['speed']
        new_x_write = np.linspace(0, write_time.iloc[-1], 1500)
        new_y_write = np.interp(new_x_write, write_time, write_speed)

        read_time = read_test['total_time']
        read_speed = read_test['speed']
        new_x_read = np.linspace(0, read_time.iloc[-1], 1500)
        new_y_read = np.interp(new_x_read, read_time, read_speed)

        fig1, ax1 = plt.subplots(figsize=(18, 10))
        ax1.set_title(f"Комбинированный график цикла {i + 1}", fontsize=22)
        ax1.plot(new_x_write, new_y_write,
                 label=f"{labels[1]} ({write_test['speed_dim'].iloc[0]})", color=colors[1])
        ax1.plot(new_x_read, new_y_read,
                 label=f"{labels[0]} ({read_test['speed_dim'].iloc[0]})", color=colors[0])
        ax1.set_xlabel("Время", fontsize=20)
        ax1.set_ylabel("Скорость", fontsize=20)
        ax1.grid(which='minor', color='0.85')
        ax1.minorticks_on()
        ax1.grid(which='major', color='0.5')
        ax1.tick_params(axis='both', which='major', labelsize=18)
        ax1.set_ylim(ymin=0)
        ax1.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: format_time(x)))
        ax1.legend(fontsize=18)
        fig1.savefig(f"temp/combined_{i + 1}.png")

        write_percent = write_test['percent']
        new_x_write_p = np.linspace(0, write_percent.iloc[-1], 1500)
        new_y_write_p = np.interp(new_x_write_p, write_percent, write_speed)

        read_percent = read_test['percent']
        new_x_read_p = np.linspace(0, read_percent.iloc[-1], 1500)
        new_y_read_p = np.interp(new_x_read_p, read_percent, read_speed)

        fig2, ax2 = plt.subplots(figsize=(18, 10))
        ax2.set_title(f"Комбинированный график цикла {i + 1}", fontsize=22)
        ax2.plot(new_x_write_p, new_y_write_p,
                 label=f"{labels[1]} ({write_test['speed_dim'].iloc[0]})", color=colors[1])
        ax2.plot(new_x_read_p, new_y_read_p,
                 label=f"{labels[0]} ({read_test['speed_dim'].iloc[0]})", color=colors[0])
        ax2.set_xlabel("Объем накопителя в %", fontsize=20)
        ax2.set_ylabel("Скорость", fontsize=20)
        ax2.grid(which='minor', color='0.85')
        ax2.minorticks_on()
        ax2.grid(which='major', color='0.5')
        ax2.tick_params(axis='both', which='major', labelsize=18)
        ax2.set_ylim(ymin=0)
        ax2.legend(fontsize=18)
        fig2.savefig(f"temp/combined_percent_{i + 1}.png")

        plt.close("all")


def delete_images(folder_path: str = "temp") -> None:
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception:
            print(f"Ошибка при удалении файла {file_path}")


def mean_speed(df_tests: list) -> Tuple[float, float]:
    all_read_speeds, all_write_speeds = [], []
    for i in range(len(df_tests)):
        current_test = df_tests[i]
        if "Запись" in current_test['test_name'].iloc[-1]:
            all_write_speeds.extend(current_test['speed'])
            continue
        all_read_speeds.extend(current_test['speed'])
    return round(pd.Series(all_write_speeds).mean(), 1), round(pd.Series(all_read_speeds).mean(), 1)


def min_speed(df_tests: list) -> Tuple[float, float]:
    all_read_speeds, all_write_speeds = [], []
    for i in range(len(df_tests)):
        current_test = df_tests[i]
        if "Запись" in current_test['test_name'].iloc[-1]:
            all_write_speeds.extend(current_test['speed'])
            continue
        all_read_speeds.extend(current_test['speed'])
    return round(pd.Series(all_write_speeds).min(), 1), round(pd.Series(all_read_speeds).min(), 1)


def max_speed(df_tests: list) -> Tuple[float, float]:
    all_read_speeds, all_write_speeds = [], []
    for i in range(len(df_tests)):
        current_test = df_tests[i]
        if "Запись" in current_test['test_name'].iloc[-1]:
            all_write_speeds.extend(current_test['speed'])
            continue
        all_read_speeds.extend(current_test['speed'])
    return round(pd.Series(all_write_speeds).max(), 1), round(pd.Series(all_read_speeds).max(), 1)


def mean_cycle_time(df_tests: list) -> str:
    all_time = [df_tests[i]['total_time'].iloc[-1] for i in range(len(df_tests))]
    mean_time = round(sum(all_time) / len(all_time))
    spread = round(((max(all_time) - min(all_time)) / mean_time) * 100, 2)
    return f"{format_time(mean_time)}\n±{spread}%"


def format_blocks(blocks: int, block_size: int) -> str:
    size_kb = blocks * block_size

    if size_kb >= 1024 * 1024 * 1024:
        return f"{size_kb / 1024 / 1024 / 1024:.2f} ТБ"
    elif size_kb >= 1024 * 1024:
        return f"{size_kb / 1024 / 1024:.2f} ГБ"
    elif size_kb >= 1024:
        return f"{size_kb / 1024:.2f} МБ"
    return f"{size_kb} кБ"


def format_time(total_seconds: int) -> str:
    total_seconds = int(total_seconds)
    if total_seconds < 3600:
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    else:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def create_pdf(all_tests: FileInfo, file_name: str, output_dir: str = None, combined: bool = False) -> None:
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{os.path.splitext(file_name)[0]}.pdf")

    else:
        output_path = f"{os.path.splitext(file_name)[0]}.pdf"

    tests, name, blocks, complete = (all_tests.all_tests, all_tests.mode,
                                     all_tests.total_blocks, all_tests.complete)
    df_tests = [calculate_speed(tests[i], all_tests.block_size) for i in range(len(tests))]
    dim_r, dim_w = "", ""

    tests_table = [
        ["Номер\nтеста", "Тип теста", "Время\nтестирования", "Средняя\nскорость",
         "Минимальная\nскорость", "Максимальная\nскорость"]]
    for i in range(len(tests)):
        current_test = df_tests[i]

        if "Запись" in current_test['test_name'].iloc[-1]:
            dim_w = current_test['speed_dim'].iloc[-1]
        else:
            dim_r = current_test['speed_dim'].iloc[-1]

        speed_dim = current_test['speed_dim'].iloc[-1]
        total_time = current_test['total_time'].iloc[-1]
        time_string = format_time(total_time)
        tests_table.append(
            [i + 1, current_test['test_name'].iloc[-1], time_string,
             f"{round(current_test['speed'].mean(), 1)} {speed_dim}",
             f"{round(current_test['speed'].min(), 1)} {speed_dim}",
             f"{round(current_test['speed'].max(), 1)} {speed_dim}"]
        )

    plots(df_tests, combined=combined)
    generator = PDFGenerator(output_path)
    generator.add_title(f"Отчет {file_name}")
    total_time = (df_tests[-1]['hours'].iloc[-1] * 3600 +
                  df_tests[-1]['minutes'].iloc[-1] * 60 + df_tests[-1]['seconds'].iloc[-1])
    time_string = format_time(total_time)
    max_write, max_read = max_speed(df_tests)
    min_write, min_read = min_speed(df_tests)
    mean_write, mean_read = mean_speed(df_tests)
    mean_time = mean_cycle_time(df_tests)
    complete_test = "Пройдено" if complete else "Провалено"
    generator.add_table([
        ["Параметр", "Чтение", "Запись"],
        ["Название исходного файла", file_name],
        ["Дата генерации отчета", date.today().strftime("%d/%m/%Y")],
        ["Объем накопителя", f"{blocks:,} блоков\n{format_blocks(blocks, all_tests.block_size)}"],
        ["Режим тестирования", name.capitalize()],
        ["Результат тестирования", complete_test],
        ["Общее время тестирования", time_string],
        ["Количество проходов чтения\nи записи", len(tests)],
        ["Среднее время одного цикла\nчтения и записи", mean_time],
        ["Средняя скорость чтения и записи", f"{mean_read} {dim_r}", f"{mean_write} {dim_w}"],
        ["Минимальная скорость чтения\nи записи", f"{min_read} {dim_r}", f"{min_write} {dim_w}"],
        ["Максимальная скорость чтения\nи записи", f"{max_read} {dim_r}", f"{max_write} {dim_w}"]
    ])
    generator.add_page_break()

    generator.add_table(tests_table, style="tests_table")

    for i in range(len(tests)):
        generator.add_image(f"temp/test{i + 1}.png")
        generator.add_image(f"temp/test{i + 1}_percent.png")

    if combined:
        generator.add_page_break()

        combined_files = []
        for file_name in os.listdir("temp"):
            if file_name.startswith("combined") and file_name.endswith(".png"):
                combined_files.append(file_name)

        combined_files.sort()

        for combined_file in combined_files:
            generator.add_image(f"temp/{combined_file}")

    generator.generate()
    delete_images()


def process_file(file_path: str, output_dir: str = None, combined: bool = False) -> bool:
    tests_file = read_file(file_path)
    if tests_file is None:
        return False

    create_pdf(tests_file, os.path.basename(file_path), output_dir, combined)

    return True


def process_directory(directory: str, output_dir: str = None, combined: bool = False) -> None:
    if not os.path.exists(directory):
        print(f"Каталог {directory} не существует")
        return None

    found_files = False
    for file in os.listdir(directory):
        if file.endswith(".bbl") or file.endswith(".log"):
            file_path = os.path.join(directory, file)
            print(f"Файл: {file_path}")
            if process_file(file_path, output_dir, combined):
                print("Отчет успешно сгенерирован\n")
                found_files = True
            else:
                print("Отчет не был сгенерирован")

    if not found_files:
        print(f"В каталоге {directory} не найдено файлов с расширением .bbl или .log")

    return None


def main() -> None:
    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-f", "--file", type=str, help="Файл для обработки (.bbl или .log)")
    group.add_argument("-d", "--directory", type=str, help="Каталог с файлами для обработки")

    parser.add_argument("-o", "--output", type=str, help="Каталог для сохранения отчетов")
    parser.add_argument("-c", "--combined", action="store_true",
                        help="Создание комбинированных графиков для циклов чтения+записи")

    args = parser.parse_args()

    if args.file:
        print(f"Файл: {args.file}")
        if process_file(args.file, output_dir=args.output, combined=args.combined):
            print("Отчет успешно сгенерирован\n")
            return
        print("Отчет не был сгенерирован")

    elif args.directory:
        process_directory(args.directory, output_dir=args.output, combined=args.combined)
        return

    else:
        print("Не указан файл или каталог для обработки. Используйте --help")


if __name__ == "__main__":
    main()
