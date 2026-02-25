import argparse
import re
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Регулярка для проверки формата URL
URL_REGEX = re.compile(r"^https://[A-Za-z0-9.-]+(?:/[^\s]*)?$")


def validate_host(url: str) -> bool:
    # Проверяем, что адрес подходит под формат https://example.com
    return bool(URL_REGEX.match(url))


def load_hosts_from_file(path: str):
    # Читаем файл со списком хостов построчно
    try:
        with open(path, "r", encoding="utf-8") as f:
            hosts = [line.strip() for line in f if line.strip()]
        return hosts
    except Exception as e:
        raise ValueError(f"Ошибка чтения файла '{path}': {e}")


def perform_request(url: str):
    # Делаем HTTP‑запрос и замеряем время
    start = time.perf_counter()
    try:
        response = requests.get(url, timeout=5)
        elapsed = time.perf_counter() - start
        return response.status_code, elapsed
    except requests.exceptions.RequestException:
        return None, None


def print_stats(stats, output_file=None):
    # Формируем удобный вывод статистики
    lines = []
    for host, data in stats.items():
        lines.append(f"Host: {host}")
        lines.append(f"  Success: {data['success']}")
        lines.append(f"  Failed:  {data['failed']}")
        lines.append(f"  Errors:  {data['errors']}")

        if data["times"]:
            lines.append(f"  Min: {min(data['times']):.4f} s")
            lines.append(f"  Max: {max(data['times']):.4f} s")
            lines.append(f"  Avg: {sum(data['times']) / len(data['times']):.4f} s")
        else:
            lines.append("  Min: -")
            lines.append("  Max: -")
            lines.append("  Avg: -")

        lines.append("")

    output = "\n".join(lines)

    # Пишем в файл или выводим в консоль
    if output_file:
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(output)
        except Exception as e:
            print(f"Ошибка записи в файл '{output_file}': {e}")
    else:
        print(output)


def main():
    # Разбираем аргументы командной строки
    parser = argparse.ArgumentParser(description="HTTP benchmark tool")
    parser.add_argument("-H", "--hosts", help="Список хостов через запятую")
    parser.add_argument("-C", "--count", type=int, default=1, help="Количество запросов (по умолчанию 1)")
    parser.add_argument("-F", "--file", help="Файл со списком хостов")
    parser.add_argument("-O", "--output", help="Файл для сохранения результата")

    args = parser.parse_args()

    # Нельзя использовать одновременно -H и -F
    if args.hosts and args.file:
        print("Ошибка: нельзя использовать одновременно -H и -F.")
        return

    # Получаем список хостов
    if args.file:
        try:
            hosts = load_hosts_from_file(args.file)
        except ValueError as e:
            print(e)
            return
    elif args.hosts:
        hosts = args.hosts.split(",")
    else:
        print("Ошибка: необходимо указать -H или -F.")
        return

    # Проверяем формат каждого URL
    for h in hosts:
        if not validate_host(h):
            print(f"Ошибка: некорректный формат URL '{h}'. Ожидается https://example.com")
            return

    # Проверяем, что count > 0
    if args.count < 1:
        print("Ошибка: параметр count должен быть положительным числом.")
        return

    # Заготовка для статистики по каждому хосту
    stats = {
        host: {"success": 0, "failed": 0, "errors": 0, "times": []}
        for host in hosts
    }

    # Параллельное выполнение запросов
    with ThreadPoolExecutor() as pool:
        # Создаём задачи для всех запросов
        futures = {
            pool.submit(perform_request, host): host
            for host in hosts
            for _ in range(args.count)
        }

        # Обрабатываем результаты по мере готовности
        for future in as_completed(futures):
            host = futures[future]
            status, elapsed = future.result()

            if status is None:
                stats[host]["errors"] += 1
                continue

            if 200 <= status < 400:
                stats[host]["success"] += 1
                stats[host]["times"].append(elapsed)
            elif 400 <= status < 600:
                stats[host]["failed"] += 1
            else:
                stats[host]["errors"] += 1

    # Выводим итоговую статистику
    print_stats(stats, args.output)


if __name__ == "__main__":
    main()
