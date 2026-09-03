"""Lightweight custom widget set (Button, TextInput, Dropdown, Toggle, Slider,
Panel, ScrollList) matching the ChessMaster theme.

Written without external deps so it stays consistent across all screens.
"""
import time
import pygame


class Widget:
    def __init__(self, rect):
        self.rect = pygame.Rect(rect)
        self.visible = True
        self.enabled = True

    def handle_event(self, e):  # override
        return False

    def draw(self, surf, theme, assets):  # override
        pass


# ---------- Button ----------
class Button(Widget):
    def __init__(self, rect, label, on_click, primary=False, icon=None,
                 font_size=16, tooltip=""):
        super().__init__(rect)
        self.label = label
        self.on_click = on_click
        self.primary = primary
        self.icon = icon
        self.font_size = font_size
        self.tooltip = tooltip
        self.hover = False
        self.pressed = False
        self._hover_t = 0

    def handle_event(self, e):
        if not self.visible or not self.enabled:
            return False
        if e.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(e.pos)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.rect.collidepoint(e.pos):
                self.pressed = True
                return True
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            was = self.pressed
            self.pressed = False
            if was and self.rect.collidepoint(e.pos):
                if self.on_click:
                    self.on_click()
                return True
        return False

    def draw(self, surf, theme, assets):
        if not self.visible:
            return
        c = theme.c
        if self.primary:
            base = c["accent_hi"] if self.hover else c["accent"]
        else:
            base = c["panel_hi"] if self.hover else c["panel"]
        if self.pressed:
            base = tuple(max(0, x - 15) for x in base)
        pygame.draw.rect(surf, base, self.rect, border_radius=8)
        pygame.draw.rect(surf, c["border"], self.rect, width=1, border_radius=8)
        font = assets.get_font(self.font_size, bold=self.primary)
        text_col = (255, 255, 255) if self.primary else c["text"]
        text = font.render(self.label, True, text_col)
        surf.blit(text, text.get_rect(center=self.rect.center))


# ---------- TextInput ----------
class TextInput(Widget):
    def __init__(self, rect, placeholder="", password=False, max_len=64,
                 on_submit=None):
        super().__init__(rect)
        self.text = ""
        self.placeholder = placeholder
        self.password = password
        self.max_len = max_len
        self.focused = False
        self.on_submit = on_submit
        self._cursor_blink = time.time()

    def handle_event(self, e):
        if not self.visible or not self.enabled:
            return False
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.focused = self.rect.collidepoint(e.pos)
            return self.focused
        if e.type == pygame.KEYDOWN and self.focused:
            if e.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.on_submit:
                    self.on_submit()
            elif e.key == pygame.K_TAB:
                self.focused = False
            elif e.unicode and e.unicode.isprintable() and len(self.text) < self.max_len:
                self.text += e.unicode
            return True
        return False

    def draw(self, surf, theme, assets):
        if not self.visible:
            return
        c = theme.c
        border = c["accent"] if self.focused else c["border"]
        pygame.draw.rect(surf, c["bg_alt"], self.rect, border_radius=6)
        pygame.draw.rect(surf, border, self.rect, width=2, border_radius=6)
        font = assets.get_font(16)
        display = ("*" * len(self.text)) if self.password else self.text
        if not display:
            text = font.render(self.placeholder, True, c["text_faint"])
        else:
            text = font.render(display, True, c["text"])
        surf.blit(text, (self.rect.x + 10,
                         self.rect.y + (self.rect.h - text.get_height()) // 2))
        if self.focused and (time.time() * 2) % 2 < 1:
            cx = self.rect.x + 10 + (text.get_width() if display else 0) + 2
            pygame.draw.line(surf, c["text"],
                             (cx, self.rect.y + 6),
                             (cx, self.rect.bottom - 6), 2)


# ---------- Toggle ----------
class Toggle(Widget):
    def __init__(self, rect, label, value=False, on_change=None):
        super().__init__(rect)
        self.label = label
        self.value = value
        self.on_change = on_change

    def handle_event(self, e):
        if not self.visible or not self.enabled:
            return False
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.rect.collidepoint(e.pos):
                self.value = not self.value
                if self.on_change:
                    self.on_change(self.value)
                return True
        return False

    def draw(self, surf, theme, assets):
        if not self.visible:
            return
        c = theme.c
        font = assets.get_font(15)
        lbl = font.render(self.label, True, c["text"])
        surf.blit(lbl, (self.rect.x, self.rect.y + 3))
        sw_w, sw_h = 42, 22
        sw_x = self.rect.right - sw_w
        sw_y = self.rect.y + 2
        col = c["accent"] if self.value else c["chip"]
        pygame.draw.rect(surf, col, (sw_x, sw_y, sw_w, sw_h), border_radius=11)
        knob_x = sw_x + (sw_w - sw_h) if self.value else sw_x
        pygame.draw.circle(surf, (255, 255, 255),
                           (knob_x + sw_h // 2, sw_y + sw_h // 2), sw_h // 2 - 2)


# ---------- Dropdown ----------
class Dropdown(Widget):
    def __init__(self, rect, options, current, on_change, label=""):
        super().__init__(rect)
        self.options = list(options)
        self.current = current if current in self.options else (self.options[0] if self.options else "")
        self.on_change = on_change
        self.label = label
        self.open = False
        self.scroll = 0
        self.max_visible = 8

    def handle_event(self, e):
        if not self.visible or not self.enabled:
            return False
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.rect.collidepoint(e.pos):
                self.open = not self.open
                return True
            if self.open:
                h = 26
                visible = min(self.max_visible, len(self.options))
                for i in range(visible):
                    idx = self.scroll + i
                    if idx >= len(self.options): break
                    r = pygame.Rect(self.rect.x, self.rect.bottom + 2 + i * h,
                                    self.rect.w, h)
                    if r.collidepoint(e.pos):
                        self.current = self.options[idx]
                        if self.on_change:
                            self.on_change(self.current)
                        self.open = False
                        return True
                self.open = False
        elif e.type == pygame.MOUSEWHEEL and self.open:
            self.scroll = max(0, min(len(self.options) - self.max_visible,
                                     self.scroll - e.y))
        return False

    def draw(self, surf, theme, assets):
        if not self.visible: return
        c = theme.c
        if self.label:
            font_s = assets.get_font(12)
            lbl = font_s.render(self.label, True, c["text_dim"])
            surf.blit(lbl, (self.rect.x, self.rect.y - 16))
        pygame.draw.rect(surf, c["panel_hi"], self.rect, border_radius=6)
        pygame.draw.rect(surf, c["border"], self.rect, width=1, border_radius=6)
        font = assets.get_font(15)
        text = font.render(str(self.current).replace("_", " ").title(), True, c["text"])
        surf.blit(text, (self.rect.x + 10,
                         self.rect.y + (self.rect.h - text.get_height()) // 2))
        ax, ay = self.rect.right - 14, self.rect.centery
        pygame.draw.polygon(surf, c["text_dim"],
                            [(ax - 5, ay - 3), (ax + 5, ay - 3), (ax, ay + 4)])

    def draw_open(self, surf, theme, assets):
        if not self.open or not self.visible: return
        c = theme.c
        h = 26
        visible = min(self.max_visible, len(self.options))
        list_rect = pygame.Rect(self.rect.x, self.rect.bottom + 2,
                                self.rect.w, h * visible)
        pygame.draw.rect(surf, c["panel_hi"], list_rect, border_radius=6)
        pygame.draw.rect(surf, c["border"], list_rect, width=1, border_radius=6)
        font = assets.get_font(14)
        mouse = pygame.mouse.get_pos()
        for i in range(visible):
            idx = self.scroll + i
            if idx >= len(self.options): break
            item = pygame.Rect(list_rect.x, list_rect.y + i * h,
                               list_rect.w, h)
            if item.collidepoint(mouse):
                pygame.draw.rect(surf, c["accent"], item)
            text_col = (255, 255, 255) if item.collidepoint(mouse) else c["text"]
            t = font.render(str(self.options[idx]).replace("_", " ").title(),
                            True, text_col)
            surf.blit(t, (item.x + 10, item.y + 5))


# ---------- Slider ----------
class Slider(Widget):
    def __init__(self, rect, minimum, maximum, value, on_change, label=""):
        super().__init__(rect)
        self.min = minimum
        self.max = maximum
        self.value = value
        self.on_change = on_change
        self.label = label
        self.dragging = False

    def _val_from_x(self, x):
        p = max(0, min(1, (x - self.rect.x) / max(1, self.rect.w)))
        return int(self.min + p * (self.max - self.min))

    def handle_event(self, e):
        if not self.visible or not self.enabled: return False
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.collidepoint(e.pos):
            self.dragging = True
            self.value = self._val_from_x(e.pos[0])
            if self.on_change: self.on_change(self.value)
            return True
        elif e.type == pygame.MOUSEMOTION and self.dragging:
            self.value = self._val_from_x(e.pos[0])
            if self.on_change: self.on_change(self.value)
            return True
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.dragging = False
        return False

    def draw(self, surf, theme, assets):
        if not self.visible: return
        c = theme.c
        if self.label:
            font_s = assets.get_font(12)
            lbl = font_s.render(f"{self.label}: {self.value}", True, c["text_dim"])
            surf.blit(lbl, (self.rect.x, self.rect.y - 16))
        track = pygame.Rect(self.rect.x, self.rect.centery - 3, self.rect.w, 6)
        pygame.draw.rect(surf, c["chip"], track, border_radius=3)
        p = (self.value - self.min) / max(1, (self.max - self.min))
        fill = pygame.Rect(self.rect.x, self.rect.centery - 3,
                           int(self.rect.w * p), 6)
        pygame.draw.rect(surf, c["accent"], fill, border_radius=3)
        cx = self.rect.x + int(self.rect.w * p)
        pygame.draw.circle(surf, (255, 255, 255), (cx, self.rect.centery), 8)
        pygame.draw.circle(surf, c["accent"], (cx, self.rect.centery), 8, 2)


# ---------- ScrollList ----------
class ScrollList(Widget):
    """Vertical list of clickable rows with rendering callback."""
    def __init__(self, rect, row_height, items, render_row, on_click=None):
        super().__init__(rect)
        self.row_h = row_height
        self.items = items
        self.render_row = render_row
        self.on_click = on_click
        self.scroll = 0

    def set_items(self, items):
        self.items = items
        self.scroll = 0

    def _max_scroll(self):
        return max(0, len(self.items) * self.row_h - self.rect.h)

    def handle_event(self, e):
        if not self.visible: return False
        if e.type == pygame.MOUSEWHEEL and self.rect.collidepoint(pygame.mouse.get_pos()):
            self.scroll = max(0, min(self._max_scroll(),
                                     self.scroll - e.y * self.row_h))
            return True
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.collidepoint(e.pos):
            i = (e.pos[1] - self.rect.y + self.scroll) // self.row_h
            if 0 <= i < len(self.items):
                if self.on_click:
                    self.on_click(int(i), self.items[int(i)])
                return True
        return False

    def draw(self, surf, theme, assets):
        c = theme.c
        pygame.draw.rect(surf, c["bg_alt"], self.rect, border_radius=6)
        pygame.draw.rect(surf, c["border"], self.rect, width=1, border_radius=6)
        clip = surf.get_clip()
        surf.set_clip(self.rect)
        for i, item in enumerate(self.items):
            y = self.rect.y + i * self.row_h - self.scroll
            if y + self.row_h < self.rect.y or y > self.rect.bottom:
                continue
            row_rect = pygame.Rect(self.rect.x, y, self.rect.w, self.row_h)
            hover = row_rect.collidepoint(pygame.mouse.get_pos()) and self.rect.collidepoint(pygame.mouse.get_pos())
            if hover:
                pygame.draw.rect(surf, c["panel_hi"], row_rect)
            self.render_row(surf, row_rect, i, item, theme, assets)
        surf.set_clip(clip)
        # Scrollbar
        if self._max_scroll() > 0:
            bar_h = max(20, int(self.rect.h * self.rect.h /
                                (len(self.items) * self.row_h)))
            bar_y = self.rect.y + int((self.rect.h - bar_h) *
                                      (self.scroll / self._max_scroll()))
            pygame.draw.rect(surf, c["chip"],
                             (self.rect.right - 6, bar_y, 4, bar_h), border_radius=2)


# ---------- Panel (simple container) ----------
class Panel(Widget):
    def __init__(self, rect, title=""):
        super().__init__(rect)
        self.title = title

    def draw(self, surf, theme, assets):
        c = theme.c
        pygame.draw.rect(surf, c["panel"], self.rect, border_radius=10)
        pygame.draw.rect(surf, c["border"], self.rect, width=1, border_radius=10)
        if self.title:
            font = assets.get_font(18, bold=True)
            t = font.render(self.title, True, c["text"])
            surf.blit(t, (self.rect.x + 16, self.rect.y + 12))
