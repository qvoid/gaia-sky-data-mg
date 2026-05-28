import sys


def human_readable_bytes(size_bytes):
    if size_bytes < 0:
        return "N/A"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024.0 and i < len(units) - 1:
        size /= 1024.0
        i += 1
    if i == 0:
        return f"{int(size)} B"
    return f"{size:.1f} {units[i]}"


def human_readable_nobjects(n):
    if n < 0:
        return "N/A"
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def version_int_to_string(version):
    if version <= 0:
        return "unknown"
    seq = version % 100
    rev = (version // 100) % 100
    minor = (version // 10000) % 100
    major = version // 1000000
    if seq > 0:
        return f"{major}.{minor}.{rev}.{seq}"
    return f"{major}.{minor}.{rev}"


def version_string_to_int(version_str):
    parts = version_str.lstrip('v').split('.')
    major = int(parts[0]) if len(parts) > 0 else 0
    minor = int(parts[1]) if len(parts) > 1 else 0
    rev = int(parts[2]) if len(parts) > 2 else 0
    seq = int(parts[3]) if len(parts) > 3 else 0
    return major * 1000000 + minor * 10000 + rev * 100 + seq


def version_to_zero_padded(version):
    return f"{version:08d}"


def confirm_prompt(message):
    try:
        response = input(f"{message} [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return response in ('y', 'yes')


def format_table(headers, rows, col_widths=None):
    if col_widths is None:
        col_widths = []
        for i, h in enumerate(headers):
            max_w = len(h)
            for row in rows:
                if i < len(row):
                    max_w = max(max_w, len(str(row[i])))
            col_widths.append(max_w + 2)

    header_line = ""
    for i, h in enumerate(headers):
        header_line += str(h).ljust(col_widths[i])
    lines = [header_line]

    separator = ""
    for w in col_widths:
        separator += "-" * (w - 1) + " "
    lines.append(separator.rstrip())

    for row in rows:
        line = ""
        for i, w in enumerate(col_widths):
            val = str(row[i]) if i < len(row) else ""
            line += val.ljust(w)
        lines.append(line)

    return "\n".join(lines)


def format_progress_bar(downloaded, total, speed_bps, width=30):
    if total > 0:
        pct = downloaded / total
        filled = int(width * pct)
        bar = "=" * filled + "-" * (width - filled)
        pct_str = f"{pct * 100:.1f}%"
        size_str = f"{human_readable_bytes(downloaded)} / {human_readable_bytes(total)}"
    else:
        bar = "=" * width
        pct_str = "???"
        size_str = human_readable_bytes(downloaded)

    speed_str = f"{human_readable_bytes(int(speed_bps))}/s" if speed_bps > 0 else "---"
    return f"  [{bar}] {pct_str} {size_str}  {speed_str}"
