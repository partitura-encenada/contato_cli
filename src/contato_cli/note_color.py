def _same_color(notes):
    """Devolve a cor (ex.: '#ff0000') se TODAS as notas do grupo tiverem a mesma; senão, None."""
    colors = [n[2] for n in notes if len(n) > 2]
    if len(colors) != len(notes) or len(set(colors)) != 1:
        return None
    return colors[0]

def set_terminal_color(notes):
    """Muda a cor de fundo do terminal para a cor do grupo de notas, se todas combinarem."""
    color = _same_color(notes)
    if not color:
        return
    hex_color = color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    print(f'\033[48;2;{r};{g};{b}m', end='', flush=True)

def reset_terminal_color():
    """Volta a cor de fundo do terminal ao padrão."""
    print('\033[49m', end='', flush=True)
