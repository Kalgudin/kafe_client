
# main_client.py — клиентское приложение кафе

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import ListProperty
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.popup import Popup
from kivy.uix.label import Label

from api_client import ApiClient

api = ApiClient()

Builder.load_file("client.kv")


def show_message(title, message):
    Popup(
        title=title,
        content=Label(text=str(message)),
        size_hint=(0.85, 0.4)
    ).open()


# =========================================================
# ЛОГИН
# =========================================================

class LoginScreen(Screen):

    def do_login(self):
        phone = self.ids.phone.text.strip()
        password = self.ids.password.text

        if not phone or not password:
            self.ids.msg.text = "Заполните все поля"
            return

        user = api.login(phone, password)

        if isinstance(user, dict) and user.get("id"):
            app = App.get_running_app()
            app.user = user
            app.cart = []

            self.ids.msg.text = ""
            app.root.current = "menu"
        else:
            self.ids.msg.text = "Неверный телефон или пароль"

    def do_register(self):
        App.get_running_app().root.current = "register"


# =========================================================
# РЕГИСТРАЦИЯ
# =========================================================

class RegisterScreen(Screen):

    def do_register(self):
        name = self.ids.name.text.strip()
        phone = self.ids.phone.text.strip()
        password = self.ids.password.text

        if not name or not phone or not password:
            self.ids.msg.text = "Заполните все поля"
            return

        result = api.create_user(name, phone, password)

        if isinstance(result, dict) and result.get("id"):
            self.ids.msg.text = ""
            show_message("Регистрация", "Аккаунт успешно создан!")
            App.get_running_app().root.current = "login"
        else:
            error = result.get("error", "Не удалось создать аккаунт") \
                if isinstance(result, dict) else "Ошибка сервера"

            self.ids.msg.text = str(error)


# =========================================================
# МЕНЮ
# =========================================================

class MenuScreen(Screen):

    rv_data = ListProperty([])

    def on_pre_enter(self):
        self.load_menu()

    def load_menu(self):
        menu = api.get_menu()

        self.rv_data = []

        if isinstance(menu, list):
            self.rv_data = [{"item": item} for item in menu]
        else:
            show_message("Ошибка", "Не удалось загрузить меню")

    def add_to_cart(self, item):
        if not item:
            return

        app = App.get_running_app()

        for cart_item in app.cart:
            if cart_item["id"] == item["id"]:
                cart_item["qty"] += 1
                break
        else:
            app.cart.append({
                "id": item["id"],
                "name": item["name"],
                "price": float(item["price"]),
                "qty": 1
            })

        app.root.current = "cart"

    def add_favorite(self, item):
        if not item:
            return

        app = App.get_running_app()

        if not app.user:
            return

        result = api.add_favorite(
            app.user["id"],
            item["id"]
        )

        if isinstance(result, dict) and result.get("error"):
            show_message("Ошибка", result["error"])
        else:
            show_message("Избранное", "Добавлено в избранное")

    def logout(self):
        app = App.get_running_app()

        app.user = None
        app.cart = []

        app.root.current = "login"


# =========================================================
# КОРЗИНА
# =========================================================

class CartScreen(Screen):

    rv_data = ListProperty([])

    def on_pre_enter(self):
        self.refresh()

    def refresh(self):
        app = App.get_running_app()

        self.rv_data = [
            {"item": item}
            for item in app.cart
        ]

        total = sum(
            float(item["price"]) * item["qty"]
            for item in app.cart
        )

        self.ids.total.text = f"Итого: {total:.2f}"

    def remove_item(self, item):
        if not item:
            return

        app = App.get_running_app()

        item["qty"] -= 1

        if item["qty"] <= 0:
            app.cart.remove(item)

        self.refresh()

    def place_order(self):
        app = App.get_running_app()

        if not app.user:
            show_message("Ошибка", "Сначала войдите в аккаунт")
            return

        if not app.cart:
            show_message("Корзина", "Корзина пуста")
            return

        items = [
            {
                "menu_item_id": item["id"],
                "quantity": item["qty"],
                "drink_options": ""
            }
            for item in app.cart
        ]

        delivery_method = self.ids.delivery.text

        result = api.create_order(
            app.user["id"],
            items,
            delivery_method
        )

        if not isinstance(result, dict) or not result.get("id"):
            error = result.get("error", "Не удалось создать заказ") \
                if isinstance(result, dict) else "Ошибка сервера"

            show_message("Ошибка заказа", error)
            return

        try:
            bonus = int(float(result.get("total", 0)) * 0.05)

            if bonus > 0:
                api.create_loyalty(
                    app.user["id"],
                    bonus,
                    "accrual",
                    result["id"]
                )

        except (ValueError, TypeError):
            pass

        app.cart = []

        show_message("Заказ", "Заказ успешно оформлен!")
        app.root.current = "orders"


# =========================================================
# ЗАКАЗЫ
# =========================================================

class OrdersScreen(Screen):

    rv_data = ListProperty([])

    def on_pre_enter(self):
        self.load_orders()

    def load_orders(self):
        app = App.get_running_app()

        if not app.user:
            return

        orders = api.get_orders()

        if not isinstance(orders, list):
            self.rv_data = []
            show_message("Ошибка", "Не удалось загрузить заказы")
            return

        my_orders = [
            order for order in orders
            if order.get("user_id") == app.user["id"]
        ]

        self.rv_data = [
            {"item": order}
            for order in my_orders
        ]

    def show_details(self, order):
        if not order:
            return

        full = api.get_order(order["id"])

        if not isinstance(full, dict) or not full.get("id"):
            show_message("Ошибка", "Не удалось загрузить заказ")
            return

        text = (
            f"Заказ #{full['id']}\n"
            f"Статус: {full.get('status', 'Не указан')}\n"
            f"Сумма: {full.get('total', 0)}\n"
            f"Способ: {full.get('delivery_method', 'Не указан')}\n\n"
        )

        for item in full.get("items", []):
            text += (
                f"• Блюдо {item.get('menu_item_id')} "
                f"× {item.get('quantity')} "
                f"= {item.get('price')} \n"
            )

        Popup(
            title="Детали заказа",
            content=Label(text=text),
            size_hint=(0.9, 0.7)
        ).open()


# =========================================================
# ИЗБРАННОЕ
# =========================================================

class FavoritesScreen(Screen):

    rv_data = ListProperty([])

    def on_pre_enter(self):
        self.load_favorites()

    def load_favorites(self):
        app = App.get_running_app()

        if not app.user:
            return

        favorites = api.get_favorites(app.user["id"])

        if isinstance(favorites, list):
            self.rv_data = [
                {"item": favorite}
                for favorite in favorites
            ]
        else:
            self.rv_data = []

    def delete_fav(self, favorite):
        if not favorite:
            return

        result = api.delete_favorite(favorite["id"])

        if isinstance(result, dict) and result.get("error"):
            show_message("Ошибка", result["error"])
            return

        self.load_favorites()


# =========================================================
# АКЦИИ
# =========================================================

class PromotionsScreen(Screen):

    rv_data = ListProperty([])

    def on_pre_enter(self):
        self.load_promotions()

    def load_promotions(self):
        app = App.get_running_app()

        if not app.user:
            return

        promotions = api.get_promotions(app.user["id"])

        if isinstance(promotions, list):
            self.rv_data = [
                {"item": promotion}
                for promotion in promotions
            ]
        else:
            self.rv_data = []

    def delete_promo(self, promotion):
        if not promotion:
            return

        result = api.delete_promotion(promotion["id"])

        if isinstance(result, dict) and result.get("error"):
            show_message("Ошибка", result["error"])
            return

        self.load_promotions()


# =========================================================
# БОНУСЫ
# =========================================================

class LoyaltyScreen(Screen):

    rv_data = ListProperty([])

    def on_pre_enter(self):
        self.load_loyalty()

    def load_loyalty(self):
        app = App.get_running_app()

        if not app.user:
            return

        loyalty = api.get_loyalty(app.user["id"])

        if isinstance(loyalty, list):
            self.rv_data = [
                {"item": transaction}
                for transaction in loyalty
            ]
        else:
            self.rv_data = []


# =========================================================
# ПРИЛОЖЕНИЕ
# =========================================================

class RestaurantClientApp(App):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.user = None
        self.cart = []

    def build(self):
        screen_manager = ScreenManager()

        screen_manager.add_widget(
            LoginScreen(name="login")
        )

        screen_manager.add_widget(
            RegisterScreen(name="register")
        )

        screen_manager.add_widget(
            MenuScreen(name="menu")
        )

        screen_manager.add_widget(
            CartScreen(name="cart")
        )

        screen_manager.add_widget(
            OrdersScreen(name="orders")
        )

        screen_manager.add_widget(
            FavoritesScreen(name="favorites")
        )

        screen_manager.add_widget(
            PromotionsScreen(name="promotions")
        )

        screen_manager.add_widget(
            LoyaltyScreen(name="loyalty")
        )

        return screen_manager


if __name__ == "__main__":
    RestaurantClientApp().run()
