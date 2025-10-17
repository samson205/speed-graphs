import os
import re
from typing import Union

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from pdf_generator import PDFGenerator


def read_file(file_name: str):
    with open(file_name, 'r', encoding="utf-8") as file:
        lines = file.readlines()

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
        return all_tests, mode, total_blocks, complete

    return False, mode, total_blocks, False


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
    # if not data:
    #     return None

    df = pd.DataFrame(data)
    df['total_time'] -= df['total_time'].iloc[0]
    df['blocks_processed'] = test['total_blocks'] * (df['percent'] / 100)
    df['blocks_delta'] = df['blocks_processed'].diff()

    df = df[df['blocks_delta'] > 0]
    df['time_delta'] = df['total_time'].diff()
    df = df[df['time_delta'] > 0]

    df['b_per_sec'] = (df['blocks_delta'] * 1024) / df['time_delta']
    df['kb_per_sec'] = df['b_per_sec'] / 1024
    df['mb_per_sec'] = df['kb_per_sec'] / 1024

    df['test_name'] = test['name']

    return df


def plots(df_tests: list) -> None:
    if not os.path.exists("temp"):
        os.mkdir("temp")

    for i, current_test in enumerate(df_tests):
        fig1, ax1 = plt.subplots(figsize=(18, 10))
        new_x = np.linspace(0, current_test['total_time'].iloc[-1], 1500)
        new_y = np.interp(new_x, current_test['total_time'], current_test['mb_per_sec'])
        ax1.plot(new_x, new_y)
        ax1.set_title(current_test['test_name'].iloc[0] + " (зависимость скорости от времени)", fontsize=20)
        ax1.set_xlabel('Время, сек', fontsize=18)
        ax1.set_ylabel('Скорость, МБ/сек', fontsize=18)
        ax1.grid(which='minor', color='0.85')
        ax1.minorticks_on()
        ax1.grid(which='major', color='0.5')
        ax1.tick_params(axis='both', which='major', labelsize=16)
        ax1.set_ylim(ymin=0)
        fig1.savefig(f"temp/test{i + 1}.png")

        fig2, ax2 = plt.subplots(figsize=(18, 10))
        new_x = np.linspace(0, current_test['percent'].iloc[-1], 1500)
        new_y = np.interp(new_x, current_test['percent'], current_test['mb_per_sec'])
        ax2.plot(new_x, new_y)
        ax2.set_title(current_test['test_name'].iloc[0] + " (зависимость скорости от объема)", fontsize=20)
        ax2.set_xlabel('Объем накопителя в %', fontsize=18)
        ax2.set_ylabel('Скорость, МБ/сек', fontsize=18)
        ax2.grid(which='minor', color='0.85')
        ax2.minorticks_on()
        ax2.grid(which='major', color='0.5')
        ax2.ticklabel_format(style='plain')
        ax2.tick_params(axis='both', which='major', labelsize=16)
        ax2.set_ylim(ymin=0)
        fig2.savefig(f"temp/test{i + 1}_percent.png")


def delete_images(folder_path="temp") -> None:
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception:
            print(f"Ошибка при удалении файла {file_path}")


def mean_speed(df_tests: list):
    all_write_speeds = pd.concat(df_tests[i]['mb_per_sec'] for i in range(0, len(df_tests), 2))
    all_read_speeds = pd.concat(df_tests[i]['mb_per_sec'] for i in range(1, len(df_tests), 2))
    return round(all_write_speeds.mean(), 1), round(all_read_speeds.mean(), 1)


def min_speed(df_tests: list):
    all_write_speeds = pd.concat(df_tests[i]['mb_per_sec'] for i in range(0, len(df_tests), 2))
    all_read_speeds = pd.concat(df_tests[i]['mb_per_sec'] for i in range(1, len(df_tests), 2))
    return round(all_write_speeds.min(), 1), round(all_read_speeds.min(), 1)


def max_speed(df_tests: list):
    all_write_speeds = pd.concat(df_tests[i]['mb_per_sec'] for i in range(0, len(df_tests), 2))
    all_read_speeds = pd.concat(df_tests[i]['mb_per_sec'] for i in range(1, len(df_tests), 2))
    return round(all_write_speeds.max(), 1), round(all_read_speeds.max(), 1)


def mean_cycle_time(df_tests: list):
    all_write_time = [df_tests[i]['total_time'].iloc[-1] for i in range(0, len(df_tests), 2)]
    all_read_time = [df_tests[i]['total_time'].iloc[-1] for i in range(1, len(df_tests), 2)]
    cycles = [all_write_time[i] + all_read_time[i] for i in range(len(all_write_time))]
    mean_time = round(sum(cycles) / len(cycles))
    spread = round(((max(cycles) - min(cycles)) / mean_time) * 100, 2)
    return f"{mean_time // 3600}:{(mean_time % 3600) // 60}:{mean_time % 60}\n{spread}%"


def main(file_name: str) -> bool:
    tests, name, blocks, complete = read_file(f"data/{file_name}")
    if complete:
        df_tests = [calculate_speed(tests[i]) for i in range(len(tests))]
        plots(df_tests)
        generator = PDFGenerator(f"{file_name.split('.')[0]}.pdf")
        generator.add_title()
        time_string = f"{df_tests[-1]['hours'].iloc[-1]}:{df_tests[-1]['minutes'].iloc[-1]}:{df_tests[-1]['seconds'].iloc[-1]}"
        max_write, max_read = max_speed(df_tests)
        min_write, min_read = min_speed(df_tests)
        mean_write, mean_read = mean_speed(df_tests)
        mean_time = mean_cycle_time(df_tests)
        generator.add_table([
            ['Объем\nнакопителя', 'Режим\nтестирования', 'Результат\nтестирования',
             'Общее\nвремя\nтестирования', 'Кол-во\nпроходов\nчтения и\nзаписи',
             'Среднее\nвремя\nодного цикла\nчтения и\nзаписи', 'Средняя\nскорость\nчтения и\nзаписи',
             'Минимальная\nскорость\nчтения и\nзаписи', 'Максимальная\nскорость чтения\nи записи'],
            [f'{blocks} блоков\n({blocks * 1024} байт)',
             name.capitalize(),
             'Пройдено',
             time_string,
             f"{len(tests) // 2}",
             mean_time,
             f"{mean_read}; {mean_write} МБ/с\n{mean_read * 1024}; {mean_write * 1024} кБ/с\n{mean_read * 1024 * 1024};\n{mean_write * 1024 * 1024} байт/с",
             f"{min_read}; {min_write} МБ/с\n{min_read * 1024}; {min_write * 1024} кБ/с\n{min_read * 1024 * 1024};\n{min_write * 1024 * 1024} байт/с",
             f"{max_read}; {max_write} МБ/с\n{max_read * 1024}; {max_write * 1024} кБ/с\n{max_read * 1024 * 1024};\n{max_write * 1024 * 1024} байт/с"]
        ])
        for i in range(len(tests)):
            generator.add_image(f"temp/test{i + 1}.png")
            generator.add_image(f"temp/test{i + 1}_percent.png")
        generator.generate()
        delete_images()

        return True
    else:
        generator = PDFGenerator(f"{file_name.split('.')[0]}.pdf")
        generator.add_title()
        generator.add_table([
            ['Объем\nнакопителя', 'Режим\nтестирования', 'Результат\nтестирования', 'Общее\nвремя\nтестирования',
             'Кол-во\nпроходов\nчтения и\nзаписи', 'Среднее\nвремя\nодного цикла\nчтения и\nзаписи',
             'Средняя\nскорость\nчтения и\nзаписи', 'Минимальная\nскорость\nчтения и\nзаписи',
             'Максимальная\nскорость чтения\nи записи'],
            [f"{blocks} блоков\n({blocks * 1024} байт)",
             name.capitalize(),
             'Провалено',
             '-',
             '-',
             '-',
             '-',
             '-',
             '-']
        ])

        generator.generate()

        return False


if __name__ == "__main__":
    fname = input('Введите имя файла в папке data: ')
    if main(fname):
        print("Отчет успешно сгенерирован")
    else:
        print("Тест не был пройден")
