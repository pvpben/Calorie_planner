import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
import datetime

# 設定現代化外觀主題
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class DatabaseManager:
    """負責管理 SQLite 資料庫的類別"""
    def __init__(self, db_name="nutrition_data.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()
        self.seed_user_data()

    def create_tables(self):
        # 1. 食材資料表
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS foods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                carbs REAL NOT NULL,
                protein REAL NOT NULL,
                fat REAL NOT NULL,
                calories REAL NOT NULL,
                price REAL NOT NULL
            )
        """)
        # 2. 每日餐期規劃資料表
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_plans (
                date TEXT,
                meal TEXT,
                name TEXT,
                qty REAL
            )
        """)
        self.conn.commit()

    def get_default_items(self):
        return [
            ("吐司一片", 26.0, 4.0, 0.0, 120.0, 10.0),       
            ("腿肉排1份", 0.0, 35.0, 30.0, 410.0, 70.0),     
            ("雞蛋一顆", 0.0, 6.0, 5.0, 69.0, 6.0),          
            ("泡麵一包", 45.0, 5.0, 15.0, 335.0, 15.0),      
            ("炸三節翅一隻", 5.0, 15.0, 15.0, 215.0, 20.0),  
            ("椰果奶茶一杯", 65.0, 0.0, 20.0, 440.0, 55.0),  
            ("可樂600ml", 63.0, 0.0, 0.0, 252.0, 35.0),      
            ("水餃一顆", 5.0, 1.5, 2.0, 44.0, 145.0),        
            ("增肌蛋白餐一盒", 71.0, 31.0, 19.0, 579.0, 99.0),
            ("鍋燒意麵套餐", 90.0, 30.0, 30.0, 750.0, 100.0), 
            ("貝納頌一瓶", 23.0, 4.0, 6.0, 162.0, 35.0),     
            #("蛋白粉一匙", 2.0, 21.0, 1.0, 101.0, 33.0)      
        ]

    def seed_user_data(self):
        default_foods = self.get_default_items()
        self.cursor.executemany("""
            INSERT OR IGNORE INTO foods (name, carbs, protein, fat, calories, price)
            VALUES (?, ?, ?, ?, ?, ?)
        """, default_foods)
        self.conn.commit()

    def reset_to_user_defaults(self):
        self.cursor.execute("DELETE FROM foods")
        self.seed_user_data()

    def get_all_foods(self):
        self.cursor.execute("SELECT name, carbs, protein, fat, calories, price FROM foods ORDER BY id ASC")
        return self.cursor.fetchall()

    def get_food_dict(self):
        rows = self.get_all_foods()
        return {
            row[0]: {
                "carbs": row[1], "protein": row[2], "fat": row[3],
                "calories": row[4], "price": row[5]
            } for row in rows
        }

    def add_or_update_food(self, name, carbs, protein, fat, calories, price):
        self.cursor.execute("""
            INSERT INTO foods (name, carbs, protein, fat, calories, price)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                carbs=excluded.carbs,
                protein=excluded.protein,
                fat=excluded.fat,
                calories=excluded.calories,
                price=excluded.price
        """, (name, carbs, protein, fat, calories, price))
        self.conn.commit()

    def delete_food(self, name):
        self.cursor.execute("DELETE FROM foods WHERE name = ?", (name,))
        self.conn.commit()

    def load_daily_plan(self, date_str, food_dict, meal_categories):
        self.cursor.execute("SELECT meal, name, qty FROM daily_plans WHERE date = ?", (date_str,))
        rows = self.cursor.fetchall()
        plan = {meal: [] for meal in meal_categories}
        
        for meal, name, qty in rows:
            if meal in plan and name in food_dict:
                info = food_dict[name]
                plan[meal].append({
                    "name": name, 
                    "qty": qty, 
                    "carbs": round(info["carbs"] * qty, 1), 
                    "protein": round(info["protein"] * qty, 1),
                    "fat": round(info["fat"] * qty, 1), 
                    "calories": round(info["calories"] * qty, 1), 
                    "price": round(info["price"] * qty, 1)
                })
        return plan

    def save_daily_plan(self, date_str, plan_dict):
        self.cursor.execute("DELETE FROM daily_plans WHERE date = ?", (date_str,))
        for meal, items in plan_dict.items():
            for item in items:
                self.cursor.execute("""
                    INSERT INTO daily_plans (date, meal, name, qty) 
                    VALUES (?, ?, ?, ?)
                """, (date_str, meal, item["name"], item["qty"]))
        self.conn.commit()


class ScrollableDropdown:
    """為下拉選單提供自訂滾動滑條 (Scrollbar) 的彈出清單元件"""
    def __init__(self, attach_widget, values=None, width=None, height=200, font_family="Microsoft JhengHei", font_size=12):
        self.attach = attach_widget
        self.values = values or []
        self.width = width
        self.height = height
        self.font_family = font_family
        self.font_size = font_size
        self.popup = None

        # 攔截 CTkComboBox 原生的選單開啟事件
        if hasattr(self.attach, "_open_dropdown_menu"):
            self.attach._open_dropdown_menu = self.toggle_dropdown
        if hasattr(self.attach, "_entry"):
            self.attach._entry.bind("<Button-1>", lambda e: self.show_dropdown(), add="+")

        # 點擊其他地方時關閉清單
        self.attach.winfo_toplevel().bind("<Button-1>", self._check_click_outside, add="+")

    def show_dropdown(self):
        if self.popup and self.popup.winfo_exists():
            self.close()
            return

        self.attach.update_idletasks()
        root_x = self.attach.winfo_rootx()
        root_y = self.attach.winfo_rooty() + self.attach.winfo_height() + 2
        w = self.width or max(self.attach.winfo_width(), 200)

        # 避免清單超出螢幕底部
        screen_h = self.attach.winfo_screenheight()
        if root_y + self.height > screen_h - 40:
            root_y = self.attach.winfo_rooty() - self.height - 2

        self.popup = tk.Toplevel(self.attach)
        self.popup.wm_overrideredirect(True)
        self.popup.wm_geometry(f"{w}x{self.height}+{root_x}+{root_y}")
        self.popup.attributes("-topmost", True)

        container = tk.Frame(self.popup, bg="#334155", bd=1)
        container.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(container, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self.listbox = tk.Listbox(
            container,
            yscrollcommand=scrollbar.set,
            bg="#1e293b",
            fg="#f8fafc",
            selectbackground="#0284c7",
            selectforeground="#ffffff",
            activestyle="none",
            highlightthickness=0,
            bd=0,
            font=(self.font_family, self.font_size)
        )
        self.listbox.pack(side="left", fill="both", expand=True, padx=(3, 0), pady=3)
        scrollbar.config(command=self.listbox.yview)

        for item in self.values:
            self.listbox.insert(tk.END, f"  {item}")

        curr_val = self.attach.get().strip()
        if curr_val in self.values:
            idx = self.values.index(curr_val)
            self.listbox.selection_set(idx)
            self.listbox.see(idx)

        def on_select(event=None):
            sel = self.listbox.curselection()
            if sel:
                chosen = self.values[sel[0]]
                self.attach.set(chosen)
                if hasattr(self.attach, "_command") and self.attach._command:
                    try:
                        self.attach._command(chosen)
                    except Exception:
                        pass
            self.close()

        def on_mousewheel(event):
            delta = -1 if event.delta > 0 else 1
            self.listbox.yview_scroll(delta * 2, "units")
            return "break"  # 阻止滾動事件傳遞至外層 CTkScrollableFrame

        self.listbox.bind("<ButtonRelease-1>", on_select)
        self.listbox.bind("<Return>", on_select)
        self.listbox.bind("<MouseWheel>", on_mousewheel)
        self.popup.bind("<Escape>", lambda e: self.close())

    def _check_click_outside(self, event):
        if self.popup and self.popup.winfo_exists():
            x, y = event.x_root, event.y_root
            px, py = self.popup.winfo_rootx(), self.popup.winfo_rooty()
            pw, ph = self.popup.winfo_width(), self.popup.winfo_height()
            ax, ay = self.attach.winfo_rootx(), self.attach.winfo_rooty()
            aw, ah = self.attach.winfo_width(), self.attach.winfo_height()
            if not (px <= x <= px + pw and py <= y <= py + ph) and not (ax <= x <= ax + aw and ay <= y <= ay + ah):
                self.close()

    def close(self):
        if self.popup and self.popup.winfo_exists():
            self.popup.destroy()
            self.popup = None

    def toggle_dropdown(self):
        if self.popup and self.popup.winfo_exists():
            self.close()
        else:
            self.show_dropdown()

    def configure(self, values=None, font_family=None, font_size=None):
        if values is not None:
            self.values = values
        if font_family is not None:
            self.font_family = font_family
        if font_size is not None:
            self.font_size = font_size


class CaloriePlannerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🥗 現代化熱量與營養規劃系統 (Calorie & Macro Planner)")
        self.geometry("1200x820")
        self.minsize(1000, 700)

        self.current_font_family = "Microsoft JhengHei"
        self.current_scale = 1.0
        self.font_registry = []
        self._updating_target_calories = False  # 防止目標熱量連動時遞迴循環觸發

        self.font_map = {
            "微軟正黑體 (Microsoft JhengHei)": "Microsoft JhengHei",
            "新細明體 (PMingLiU)": "PMingLiU",
            "標楷體 (DFKai-SB)": "DFKai-SB",
            "Arial": "Arial",
            "Consolas (等寬字)": "Consolas"
        }

        self.db = DatabaseManager()
        self.calc_items = []
        self.meal_categories = ["早餐", "午餐", "下午茶", "晚餐", "點心", "消夜"]
        
        # 日期規劃記憶體結構
        self.plan_date_obj = datetime.date.today()
        self.meal_plans_db = {}
        
        self.style = ttk.Style()
        self.style.theme_use("default")
        self.update_treeview_style()

        self.init_top_settings_bar()

        self.tabview = ctk.CTkTabview(self, corner_radius=12)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(5, 15))

        self.tab_db = self.tabview.add("📦 1. 食材資料庫")
        self.tab_calc = self.tabview.add("🧮 2. 營養計算器")
        self.tab_plan = self.tabview.add("📅 3. 每日餐期規劃")

        self.scroll_db = ctk.CTkScrollableFrame(self.tab_db, fg_color="transparent")
        self.scroll_db.pack(fill="both", expand=True)
        
        self.scroll_calc = ctk.CTkScrollableFrame(self.tab_calc, fg_color="transparent")
        self.scroll_calc.pack(fill="both", expand=True)
        
        self.scroll_plan = ctk.CTkScrollableFrame(self.tab_plan, fg_color="transparent")
        self.scroll_plan.pack(fill="both", expand=True)

        self.init_db_tab()
        self.init_calc_tab()
        self.init_plan_tab()

    def register_font_widget(self, widget, base_size=13, weight="normal"):
        self.font_registry.append((widget, base_size, weight))
        widget.configure(font=(self.current_font_family, base_size, weight))

    def init_top_settings_bar(self):
        bar = ctk.CTkFrame(self, corner_radius=10, fg_color="#1e293b")
        bar.pack(fill="x", padx=20, pady=(12, 4))

        lbl_title = ctk.CTkLabel(bar, text="⚙️ 介面顯示設定：", text_color="#38bdf8")
        lbl_title.pack(side="left", padx=(15, 5), pady=8)
        self.register_font_widget(lbl_title, 14, "bold")

        lbl_font = ctk.CTkLabel(bar, text="字體：")
        lbl_font.pack(side="left", padx=(10, 4))
        self.register_font_widget(lbl_font, 13)

        self.font_combo = ctk.CTkComboBox(bar, values=list(self.font_map.keys()), width=230, command=self.on_font_family_change)
        self.font_combo.set("微軟正黑體 (Microsoft JhengHei)")
        self.font_combo.pack(side="left", padx=4)
        self.register_font_widget(self.font_combo, 12)

        lbl_scale = ctk.CTkLabel(bar, text="大小縮放 (50%~200%)：")
        lbl_scale.pack(side="left", padx=(20, 4))
        self.register_font_widget(lbl_scale, 13)

        scale_options = ["50%", "75%", "90%", "100%", "110%", "125%", "150%", "175%", "200%"]
        self.scale_combo = ctk.CTkComboBox(bar, values=scale_options, width=100, command=self.on_scale_combo_change)
        self.scale_combo.set("100%")
        self.scale_combo.pack(side="left", padx=4)
        self.register_font_widget(self.scale_combo, 12)

        self.scale_slider = ctk.CTkSlider(bar, from_=50, to=200, number_of_steps=30, width=160, command=self.on_scale_slider_drag)
        self.scale_slider.set(100)
        self.scale_slider.pack(side="left", padx=10)
        self.scale_slider.bind("<ButtonRelease-1>", self.on_scale_slider_release)

        self.scale_val_label = ctk.CTkLabel(bar, text="100%", width=50, text_color="#4ade80")
        self.scale_val_label.pack(side="left", padx=4)
        self.register_font_widget(self.scale_val_label, 13, "bold")

    def on_font_family_change(self, choice):
        self.current_font_family = self.font_map.get(choice, "Microsoft JhengHei")
        self.apply_font_and_scale()

    def on_scale_combo_change(self, choice):
        try:
            pct = int(choice.replace("%", ""))
            pct = max(50, min(200, pct))
            self.scale_slider.set(pct)
            self.scale_val_label.configure(text=f"{pct}%")
            self.current_scale = pct / 100.0
            self.apply_font_and_scale()
        except ValueError:
            pass

    def on_scale_slider_drag(self, value):
        pct = int(round(value))
        self.scale_val_label.configure(text=f"{pct}%")

    def on_scale_slider_release(self, event):
        pct = int(round(self.scale_slider.get()))
        self.scale_combo.set(f"{pct}%")
        self.current_scale = pct / 100.0
        self.apply_font_and_scale()

    def apply_font_and_scale(self):
        for widget, base_size, weight in self.font_registry:
            try:
                widget.configure(font=(self.current_font_family, base_size, weight))
            except Exception:
                pass
        self.update_treeview_style()
        ctk.set_widget_scaling(self.current_scale)
        
        # 同步更新自訂滾動清單的字體大小
        scaled_size = max(8, int(12 * self.current_scale))
        if hasattr(self, "plan_food_dropdown"):
            self.plan_food_dropdown.configure(font_family=self.current_font_family, font_size=scaled_size)

    def update_treeview_style(self):
        scaled_font_size = max(7, int(11 * self.current_scale))
        scaled_row_height = max(20, int(30 * self.current_scale))
        self.style.configure(
            "Treeview", background="#2b2b2b", foreground="white",
            rowheight=scaled_row_height, fieldbackground="#2b2b2b", borderwidth=0,
            font=(self.current_font_family, scaled_font_size)
        )
        self.style.configure(
            "Treeview.Heading", background="#1f538d", foreground="white",
            font=(self.current_font_family, scaled_font_size, "bold"), relief="flat"
        )
        self.style.map("Treeview", background=[("selected", "#3a7ebf")])

    # =========================================================================
    # 功能 1：食材資料庫
    # =========================================================================
    def init_db_tab(self):
        self.scroll_db.grid_columnconfigure(0, weight=1)
        self.scroll_db.grid_columnconfigure(1, weight=3)

        form_frame = ctk.CTkFrame(self.scroll_db, corner_radius=12)
        form_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        title_lbl = ctk.CTkLabel(form_frame, text="新增 / 修改單項食材")
        title_lbl.pack(pady=(12, 8))
        self.register_font_widget(title_lbl, 17, "bold")

        self.db_entries = {}
        fields = [
            ("name", "食材名稱 (如: 吐司一片)"), ("carbs", "碳水化合物 (g)"), ("protein", "蛋白質 (g)"),
            ("fat", "脂肪 (g)"), ("calories", "熱量 (kcal) [可自動推算]"), ("price", "單價 (NT$)")
        ]

        for key, label_text in fields:
            lbl = ctk.CTkLabel(form_frame, text=label_text)
            lbl.pack(anchor="w", padx=20, pady=(4, 0))
            self.register_font_widget(lbl, 12)
            entry = ctk.CTkEntry(form_frame, placeholder_text=f"請輸入{label_text.split()[0]}...")
            entry.pack(fill="x", padx=20, pady=(2, 4))
            self.register_font_widget(entry, 12)
            self.db_entries[key] = entry

        btn_auto = ctk.CTkButton(form_frame, text="⚡ 依三大營養自動算熱量", fg_color="#555555", command=self.auto_calc_food_calories)
        btn_auto.pack(fill="x", padx=20, pady=(8, 4))
        self.register_font_widget(btn_auto, 12)

        btn_save = ctk.CTkButton(form_frame, text="💾 儲存至資料庫", fg_color="#28a745", command=self.save_food_to_db)
        btn_save.pack(fill="x", padx=20, pady=4)
        self.register_font_widget(btn_save, 13, "bold")

        btn_del = ctk.CTkButton(form_frame, text="🗑️ 刪除選取食材", fg_color="#dc3545", command=self.delete_selected_food)
        btn_del.pack(fill="x", padx=20, pady=4)
        self.register_font_widget(btn_del, 12)

        btn_reset = ctk.CTkButton(form_frame, text="🔄 重置為預設 12 品項", fg_color="#475569", command=self.reset_default_foods)
        btn_reset.pack(fill="x", padx=20, pady=(4, 10))
        self.register_font_widget(btn_reset, 12)

        table_frame = ctk.CTkFrame(self.scroll_db, corner_radius=12)
        table_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        columns = ("name", "carbs", "protein", "fat", "calories", "price")
        self.db_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        headings = ["單項名稱", "碳水 (g)", "蛋白質 (g)", "脂肪 (g)", "熱量 (kcal)", "單價 ($)"]
        widths = [180, 90, 90, 90, 100, 90]

        for col, head, w in zip(columns, headings, widths):
            self.db_tree.heading(col, text=head)
            self.db_tree.column(col, width=w, anchor="center" if col != "name" else "w")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.db_tree.yview)
        self.db_tree.configure(yscrollcommand=scrollbar.set)
        self.db_tree.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)

        self.db_tree.bind("<<TreeviewSelect>>", self.on_db_row_select)
        self.refresh_db_ui()

    def auto_calc_food_calories(self):
        try:
            c = float(self.db_entries["carbs"].get() or 0)
            p = float(self.db_entries["protein"].get() or 0)
            f = float(self.db_entries["fat"].get() or 0)
            kcal = round(c * 4 + p * 4 + f * 9, 1)
            self.db_entries["calories"].delete(0, tk.END)
            self.db_entries["calories"].insert(0, str(kcal))
        except ValueError:
            messagebox.showwarning("輸入錯誤", "請先輸入有效的碳水、蛋白質與脂肪數字！")

    def save_food_to_db(self):
        name = self.db_entries["name"].get().strip()
        if not name: return
        try:
            carbs, protein, fat, calories, price = [float(self.db_entries[k].get()) for k in ["carbs", "protein", "fat", "calories", "price"]]
        except ValueError:
            messagebox.showerror("格式錯誤", "請輸入有效數字！")
            return
        self.db.add_or_update_food(name, carbs, protein, fat, calories, price)
        self.refresh_db_ui()
        messagebox.showinfo("成功", f"已成功儲存「{name}」！")

    def delete_selected_food(self):
        selected = self.db_tree.selection()
        if not selected: return
        name = self.db_tree.item(selected[0])["values"][0]
        if messagebox.askyesno("確認刪除", f"確定刪除「{name}」嗎？"):
            self.db.delete_food(name)
            self.refresh_db_ui()

    def reset_default_foods(self):
        if messagebox.askyesno("確認", "確定重置為預設 12 品項？"):
            self.db.reset_to_user_defaults()
            self.refresh_db_ui()

    def on_db_row_select(self, event):
        selected = self.db_tree.selection()
        if not selected: return
        values = self.db_tree.item(selected[0])["values"]
        for k, v in zip(["name", "carbs", "protein", "fat", "calories", "price"], values):
            self.db_entries[k].delete(0, tk.END)
            self.db_entries[k].insert(0, str(v))

    def refresh_db_ui(self):
        for row in self.db_tree.get_children(): self.db_tree.delete(row)
        foods = self.db.get_all_foods()
        for f in foods: self.db_tree.insert("", tk.END, values=f)
        
        food_names = [f[0] for f in foods] or ["(無資料)"]
        if hasattr(self, "calc_food_combo"):
            self.calc_food_combo.configure(values=food_names)
            self.calc_food_combo.set(food_names[0])
        if hasattr(self, "plan_food_combo"):
            self.plan_food_combo.configure(values=food_names)
            self.plan_food_combo.set(food_names[0])
        if hasattr(self, "plan_food_dropdown"):
            self.plan_food_dropdown.configure(values=food_names)

    # =========================================================================
    # 功能 2：營養計算器
    # =========================================================================
    def init_calc_tab(self):
        ctrl_frame = ctk.CTkFrame(self.scroll_calc, corner_radius=12)
        ctrl_frame.pack(fill="x", padx=10, pady=10)

        lbl_sel = ctk.CTkLabel(ctrl_frame, text="選擇食材：")
        lbl_sel.pack(side="left", padx=(15, 5), pady=15)
        self.register_font_widget(lbl_sel, 14)

        food_names = [f[0] for f in self.db.get_all_foods()] or ["(無資料)"]
        self.calc_food_combo = ctk.CTkComboBox(ctrl_frame, values=food_names, width=200)
        self.calc_food_combo.pack(side="left", padx=5)
        
        lbl_qty = ctk.CTkLabel(ctrl_frame, text="數量：")
        lbl_qty.pack(side="left", padx=(15, 5))
        self.calc_qty_entry = ctk.CTkEntry(ctrl_frame, width=70)
        self.calc_qty_entry.insert(0, "1")
        self.calc_qty_entry.pack(side="left", padx=5)

        btn_add = ctk.CTkButton(ctrl_frame, text="➕ 加入清單", command=self.add_to_calculator)
        btn_add.pack(side="left", padx=15)
        btn_rm = ctk.CTkButton(ctrl_frame, text="🗑️ 移除", fg_color="#dc3545", width=70, command=self.remove_calc_item)
        btn_rm.pack(side="left", padx=5)
        btn_clr = ctk.CTkButton(ctrl_frame, text="🔄 清空", fg_color="#6c757d", width=70, command=self.clear_calculator)
        btn_clr.pack(side="left", padx=5)

        for w in [lbl_qty, self.calc_qty_entry, btn_add, btn_rm, btn_clr, self.calc_food_combo]:
            self.register_font_widget(w, 13)

        table_frame = ctk.CTkFrame(self.scroll_calc, corner_radius=12)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("name", "qty", "carbs", "protein", "fat", "calories", "price")
        self.calc_tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=10)
        for c, h in zip(cols, ["食材名稱", "數量", "碳水(g)", "蛋白(g)", "脂肪(g)", "熱量(kcal)", "金額($)"]):
            self.calc_tree.heading(c, text=h)
            self.calc_tree.column(c, anchor="center" if c != "name" else "w", width=120)
        self.calc_tree.pack(fill="both", expand=True, padx=10, pady=10)

        summary_frame = ctk.CTkFrame(self.scroll_calc, corner_radius=12, fg_color="#1e293b")
        summary_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.calc_summary_label = ctk.CTkLabel(summary_frame, text="📊 總計結果 ➔   ...", text_color="#38bdf8")
        self.calc_summary_label.pack(pady=18)
        self.register_font_widget(self.calc_summary_label, 15, "bold")
        self.refresh_calc_ui()

    def add_to_calculator(self):
        name = self.calc_food_combo.get()
        food_dict = self.db.get_food_dict()
        if name not in food_dict: return
        try:
            qty = float(self.calc_qty_entry.get())
            if qty <= 0: raise ValueError
        except: return
        info = food_dict[name]
        self.calc_items.append({
            "name": name, "qty": qty, "carbs": info["carbs"]*qty, "protein": info["protein"]*qty,
            "fat": info["fat"]*qty, "calories": info["calories"]*qty, "price": info["price"]*qty
        })
        self.refresh_calc_ui()

    def remove_calc_item(self):
        sel = self.calc_tree.selection()
        if sel:
            self.calc_items.pop(self.calc_tree.index(sel[0]))
            self.refresh_calc_ui()

    def clear_calculator(self):
        self.calc_items.clear()
        self.refresh_calc_ui()

    def refresh_calc_ui(self):
        for row in self.calc_tree.get_children(): self.calc_tree.delete(row)
        tc=tp=tf=tcal=tpr=0.0
        for i in self.calc_items:
            self.calc_tree.insert("", tk.END, values=(i["name"], i["qty"], round(i["carbs"],1), round(i["protein"],1), round(i["fat"],1), round(i["calories"],1), round(i["price"],1)))
            tc+=i["carbs"]; tp+=i["protein"]; tf+=i["fat"]; tcal+=i["calories"]; tpr+=i["price"]
        self.calc_summary_label.configure(text=f"📊 總計 ➔  碳水: {tc:.1f} g  |  蛋白: {tp:.1f} g  |  脂肪: {tf:.1f} g  |  🔥 熱量: {tcal:.1f} kcal  |  💰 花費: ${tpr:.1f}")

    # =========================================================================
    # 功能 3：每日餐期規劃 (含熱量連動與帶滑條的選擇清單)
    # =========================================================================
    def init_plan_tab(self):
        date_bar = ctk.CTkFrame(self.scroll_plan, corner_radius=12, fg_color="#1e293b")
        date_bar.pack(fill="x", padx=10, pady=(5, 5))
        
        btn_prev = ctk.CTkButton(date_bar, text="◀ 前一天", width=80, command=self.prev_date)
        btn_prev.pack(side="left", padx=15, pady=10)
        
        self.date_lbl = ctk.CTkLabel(date_bar, text=self.get_date_str(), text_color="#f8fafc")
        self.date_lbl.pack(side="left", padx=20)
        self.register_font_widget(self.date_lbl, 16, "bold")
        
        btn_next = ctk.CTkButton(date_bar, text="後一天 ▶", width=80, command=self.next_date)
        btn_next.pack(side="left", padx=15)
        
        btn_today = ctk.CTkButton(date_bar, text="📅 回到今天", fg_color="#475569", width=100, command=self.go_today)
        btn_today.pack(side="left", padx=30)
        
        for w in [btn_prev, btn_next, btn_today]: self.register_font_widget(w, 13)

        # -- 目標需求設定區 (熱量隨三大營養一同變更) --
        top_frame = ctk.CTkFrame(self.scroll_plan, corner_radius=12)
        top_frame.pack(fill="x", padx=10, pady=5)
        target_row = ctk.CTkFrame(top_frame, fg_color="transparent")
        target_row.pack(fill="x", padx=15, pady=(10, 5))

        lbl_target = ctk.CTkLabel(target_row, text="🎯 每日目標需求設定：")
        lbl_target.pack(side="left", padx=(0, 10))
        self.register_font_widget(lbl_target, 14, "bold")

        self.target_vars = {}
        target_fields = [
            ("carbs", "目標碳水(g)", "300"), 
            ("protein", "目標蛋白(g)", "120"), 
            ("fat", "目標脂肪(g)", "65"), 
            ("calories", "目標熱量(kcal) [自動推算]", "2265")
        ]

        for key, label, val in target_fields:
            lbl = ctk.CTkLabel(target_row, text=label)
            lbl.pack(side="left", padx=(8, 2))
            sv = tk.StringVar(value=val)
            
            # 若為碳水、蛋白質、脂肪，綁定連動推算熱量的函式
            if key in ["carbs", "protein", "fat"]:
                sv.trace_add("write", self.on_target_macro_change)
            else:
                sv.trace_add("write", lambda *args: self.update_plan_dashboard())

            entry = ctk.CTkEntry(target_row, textvariable=sv, width=70)
            entry.pack(side="left", padx=4)
            self.register_font_widget(lbl, 12)
            self.register_font_widget(entry, 12)
            self.target_vars[key] = sv

        cards_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        cards_frame.pack(fill="x", padx=10, pady=(5, 10))
        for i in range(5): cards_frame.grid_columnconfigure(i, weight=1)

        self.stat_Labels = {}
        for idx, (key, title) in enumerate([("carbs", "🍞 碳水(g)"), ("protein", "🥩 蛋白(g)"), ("fat", "🥑 脂肪(g)"), ("calories", "🔥 總熱量"), ("price", "💰 預估花費")]):
            card = ctk.CTkFrame(cards_frame, corner_radius=10, fg_color="#0f172a")
            card.grid(row=0, column=idx, padx=5, sticky="nsew")
            t_lbl = ctk.CTkLabel(card, text=title, text_color="#94a3b8")
            t_lbl.pack(pady=(8, 2))
            lbl = ctk.CTkLabel(card, text="--")
            lbl.pack(pady=(2, 8))
            self.register_font_widget(t_lbl, 13, "bold")
            self.register_font_widget(lbl, 13, "bold")
            self.stat_Labels[key] = lbl

        # -- 操作列 (食材清單掛載滑條) --
        add_bar = ctk.CTkFrame(self.scroll_plan, corner_radius=12)
        add_bar.pack(fill="x", padx=10, pady=4)
        
        c1 = ctk.CTkLabel(add_bar, text="餐期：")
        c1.pack(side="left", padx=(15, 4), pady=10)
        self.plan_meal_combo = ctk.CTkComboBox(add_bar, values=self.meal_categories, width=100)
        self.plan_meal_combo.pack(side="left", padx=4)
        
        c2 = ctk.CTkLabel(add_bar, text="食材：")
        c2.pack(side="left", padx=(10, 4))
        food_names = [f[0] for f in self.db.get_all_foods()] or ["(無資料)"]
        self.plan_food_combo = ctk.CTkComboBox(add_bar, values=food_names, width=190)
        self.plan_food_combo.pack(side="left", padx=4)
        
        # 核心升級：為餐期規劃食材清單掛載自訂滾動滑條 (ScrollableDropdown)
        self.plan_food_dropdown = ScrollableDropdown(self.plan_food_combo, values=food_names, height=300)

        c3 = ctk.CTkLabel(add_bar, text="數量：")
        c3.pack(side="left", padx=(10, 4))
        self.plan_qty_entry = ctk.CTkEntry(add_bar, width=60)
        self.plan_qty_entry.insert(0, "1")
        self.plan_qty_entry.pack(side="left", padx=4)
        
        b1 = ctk.CTkButton(add_bar, text="➕ 排入", fg_color="#28a745", width=80, command=self.add_to_meal_plan)
        b1.pack(side="left", padx=15)
        b2 = ctk.CTkButton(add_bar, text="🗑️ 刪除", fg_color="#dc3545", width=80, command=self.remove_from_meal_plan)
        b2.pack(side="left", padx=4)
        b3 = ctk.CTkButton(add_bar, text="🔄 清空當日", fg_color="#6c757d", width=100, command=self.clear_all_meal_plans)
        b3.pack(side="left", padx=4)
        
        for w in [c1, self.plan_meal_combo, c2, self.plan_food_combo, c3, self.plan_qty_entry, b1, b2, b3]:
            self.register_font_widget(w, 13)

        grid_frame = ctk.CTkFrame(self.scroll_plan, corner_radius=12, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=5, pady=(4, 5))
        for r in range(2): grid_frame.grid_rowconfigure(r, weight=1)
        for c in range(3): grid_frame.grid_columnconfigure(c, weight=1)

        self.meal_trees = {}
        icons = ["🌅 早餐", "☀️ 午餐", "☕ 下午茶", "🌙 晚餐", "🍪 點心", "🦉 消夜"]
        
        for idx, meal in enumerate(self.meal_categories):
            r, c = divmod(idx, 3)
            m_frame = ctk.CTkFrame(grid_frame, corner_radius=8)
            m_frame.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")
            m_lbl = ctk.CTkLabel(m_frame, text=icons[idx], text_color="#60a5fa")
            m_lbl.pack(anchor="w", padx=10, pady=(4, 2))
            self.register_font_widget(m_lbl, 13, "bold")
            
            tree = ttk.Treeview(m_frame, columns=("name","qty","c","p","f","cal"), show="headings", height=4)
            for col, h, w in zip(("name","qty","c","p","f","cal"), ["名稱","份數","碳水","蛋白","脂肪","熱量"], [90,40,40,40,40,45]):
                tree.heading(col, text=h)
                tree.column(col, width=w, anchor="center" if col != "name" else "w")
            tree.pack(fill="both", expand=True, padx=6, pady=(0, 6))
            
            tree.bind("<<TreeviewSelect>>", lambda event, m=meal: self.on_plan_row_select(event, m))
            self.meal_trees[meal] = tree

        self.load_date_plan()

    def on_target_macro_change(self, *args):
        """當目標碳水、蛋白質或脂肪變更時，自動依三大營養素公式重算目標熱量"""
        if getattr(self, "_updating_target_calories", False):
            return
        try:
            c_str = self.target_vars["carbs"].get().strip()
            p_str = self.target_vars["protein"].get().strip()
            f_str = self.target_vars["fat"].get().strip()
            c = float(c_str) if c_str else 0.0
            p = float(p_str) if p_str else 0.0
            f = float(f_str) if f_str else 0.0
            auto_kcal = round(c * 4 + p * 4 + f * 9, 1)
            
            self._updating_target_calories = True
            cal_str = str(int(auto_kcal)) if auto_kcal.is_integer() else str(auto_kcal)
            self.target_vars["calories"].set(cal_str)
        except ValueError:
            pass
        finally:
            self._updating_target_calories = False
            
        self.update_plan_dashboard()

    def get_date_str(self):
        return self.plan_date_obj.strftime("%Y-%m-%d")

    def prev_date(self):
        self.plan_date_obj -= datetime.timedelta(days=1)
        self.date_lbl.configure(text=self.get_date_str())
        self.load_date_plan()

    def next_date(self):
        self.plan_date_obj += datetime.timedelta(days=1)
        self.date_lbl.configure(text=self.get_date_str())
        self.load_date_plan()

    def go_today(self):
        self.plan_date_obj = datetime.date.today()
        self.date_lbl.configure(text=self.get_date_str())
        self.load_date_plan()

    def load_date_plan(self):
        d_str = self.get_date_str()
        if d_str not in self.meal_plans_db:
            food_dict = self.db.get_food_dict()
            self.meal_plans_db[d_str] = self.db.load_daily_plan(d_str, food_dict, self.meal_categories)
            
        self.refresh_meal_trees()
        self.update_plan_dashboard()

    def get_current_day_plan(self):
        return self.meal_plans_db[self.get_date_str()]

    def on_plan_row_select(self, event, clicked_meal):
        tree = self.meal_trees[clicked_meal]
        selected = tree.selection()
        if not selected:
            return
            
        for m, t in self.meal_trees.items():
            if m != clicked_meal:
                for item in t.selection():
                    t.selection_remove(item)

        values = tree.item(selected[0])["values"]
        if values:
            name = values[0]
            qty = values[1]
            
            self.plan_meal_combo.set(clicked_meal)
            self.plan_food_combo.set(name)
            self.plan_qty_entry.delete(0, tk.END)
            self.plan_qty_entry.insert(0, str(qty))

    def add_to_meal_plan(self):
        meal, name = self.plan_meal_combo.get(), self.plan_food_combo.get()
        food_dict = self.db.get_food_dict()
        if name not in food_dict: return
        try:
            qty = float(self.plan_qty_entry.get())
            if qty <= 0: raise ValueError
        except: return
        
        info = food_dict[name]
        self.get_current_day_plan()[meal].append({
            "name": name, "qty": qty, "carbs": info["carbs"]*qty, "protein": info["protein"]*qty,
            "fat": info["fat"]*qty, "calories": info["calories"]*qty, "price": info["price"]*qty
        })
        
        self.db.save_daily_plan(self.get_date_str(), self.get_current_day_plan())
        self.refresh_meal_trees()
        self.update_plan_dashboard()

    def remove_from_meal_plan(self):
        day_plan = self.get_current_day_plan()
        for meal, tree in self.meal_trees.items():
            sel = tree.selection()
            if sel:
                day_plan[meal].pop(tree.index(sel[0]))
                self.db.save_daily_plan(self.get_date_str(), day_plan)
                self.refresh_meal_trees()
                self.update_plan_dashboard()
                self.plan_qty_entry.delete(0, tk.END)
                self.plan_qty_entry.insert(0, "1")
                return

    def clear_all_meal_plans(self):
        day_plan = self.get_current_day_plan()
        for meal in self.meal_categories: day_plan[meal].clear()
        self.db.save_daily_plan(self.get_date_str(), day_plan)
        self.refresh_meal_trees()
        self.update_plan_dashboard()

    def refresh_meal_trees(self):
        day_plan = self.get_current_day_plan()
        for meal, tree in self.meal_trees.items():
            for row in tree.get_children(): tree.delete(row)
            for i in day_plan[meal]:
                tree.insert("", tk.END, values=(i["name"], i["qty"], round(i["carbs"],1), round(i["protein"],1), round(i["fat"],1), round(i["calories"],1)))

    def update_plan_dashboard(self):
        totals = {"carbs": 0, "protein": 0, "fat": 0, "calories": 0, "price": 0}
        for lst in self.get_current_day_plan().values():
            for i in lst:
                for k in totals: totals[k] += i[k]

        for key in ["carbs", "protein", "fat", "calories"]:
            try: tgt = float(self.target_vars[key].get())
            except: tgt = 0
            curr = totals[key]
            diff = tgt - curr
            
            if diff > 0: txt, col = f"已排: {curr:.1f}\n⚠️ 欠缺: {diff:.1f}", "#facc15"
            elif diff < -5: txt, col = f"已排: {curr:.1f}\n🚨 超標: {abs(diff):.1f}", "#f87171"
            else: txt, col = f"已排: {curr:.1f}\n✅ 完美達標！", "#4ade80"
            self.stat_Labels[key].configure(text=txt, text_color=col)
            
        self.stat_Labels["price"].configure(text=f"今日餐費\n💵 NT$ {totals['price']:.1f}", text_color="#38bdf8")


if __name__ == "__main__":
    app = CaloriePlannerApp()
    app.mainloop()