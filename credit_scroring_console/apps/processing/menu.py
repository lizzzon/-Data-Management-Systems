# Все меню в одном файле чтобы избежать циркуляции импортов
import json
from prettytable import PrettyTable
from typing import Optional
from pydantic.error_wrappers import ValidationError
from datetime import datetime

from apps.commands.sql import SQLCommands
from apps.models.database_models import (
    ClientModel,
    UserModel,
    ProductModel,
    LoanTypeEnum,
    LoanStatusEnum,
    LoansModel,
)
from apps.templates.menu_templates import (
    CLIENT_MSG,
    LOGIN_MSG,
    REGISTER_MSG,
    START_APP_MESSAGE,
)

from apps.processing.abstract_menu import ABCMenu
from apps.templates.menu_templates import BASE_MSG

from apps.config.config import (
    current_user,
    current_client,
    current_staff,
    current_company,
)
from apps.models.database_models import UserRoleEnum


def _is_agan():
    return input('Попробуем еще разок?\n1 - Да\n0 - Нет\n') == '0'


def _pretty_result(result: list, header: list) -> PrettyTable:
    table = PrettyTable(header)
    for i in result:
        table.add_row(i)
    return table


class LogoutMenu(ABCMenu):

    def menu(self):
        print(f'Успешный выход {current_user.get().username}!')
        current_user.set(None)
        return StartMenu

# ------------------------ START BASE ------------------------------

class ClientMenu(ABCMenu):

    @staticmethod
    def _fill_information_about_yourself():
        dict_model = ClientModel().dict(exclude={'id', 'user_id',})

        print(f'Необходимо заполнить поля: {[k for k in dict_model.keys()]}')

        while True:
            for k in dict_model.keys():
                dict_model[k] = input(f"Введите {k}: ")
            try:
                client = ClientModel(**dict_model)
                break
            except ValidationError as ex:
                print(f'\nВозникла ошибка:\n{ex}\n')
                if _is_agan():
                    return ClientMenu
                continue

        user = current_user.get()

        if not user.is_active:
            user.is_active = True
            SQLCommands.update_execute(
                table='users',
                set_dict={'is_active': True},
                where_str=f'id = {user.id}',
            )

        dict_model.update({'user_id': user.id})
        SQLCommands.insert_execute(
            table='clients',
            dict_model=dict_model,
        )

        if not current_client.get():
            client = SQLCommands.select_one_execute(
                table='clients',
                where_str=f'user_id = {user.id}',
                model=ClientModel,
            )

            current_client.set(client)

        print('Успешно!\n')


    @staticmethod
    def _create_loan():
        while True:
            product_name = input('Название товара: ')

            product: Optional[ProductModel] = SQLCommands.select_one_execute(table='products', where_str=f"product_name = '{product_name}'", model=ProductModel)

            if not product:
                print('Нет такого продукта')
                if _is_agan():
                    break
                continue

            product_amount = int(input('Количество товара: '))

            if product.product_amount < product_amount:
                print(f'Слишком много, есть только {product.product_amount}')
                if _is_agan():
                    break
                continue

            dict_model = LoansModel(
                client_id=current_client.get().id,
                company_id=product.company_id,
                product_id=product.id,
                loan_status=LoanStatusEnum.created.name,
                loan_type=LoanTypeEnum.credit.name,
                order_amount=product_amount,
                credit_period=365,
                credit_rate=12,
                outstanding_loan_amount=product.product_cost * product_amount,
                credit_datetime=datetime.now(),
                last_change_datetime=datetime.now(),
            ).json(exclude={'id'})

            SQLCommands.insert_execute(
                table='loans',
                dict_model=json.loads(dict_model),
            )

            print('Успешно!')
            break

    @staticmethod
    def _view_companies():
        result = SQLCommands.custom_select_execute(
            query="""
            SELECT u.username, companies.company_name, companies.short_name FROM companies INNER JOIN users u on u.id = companies.user_id;
            """,
        )
        if not result:
            print('Ничего не нашли :(')

        header = ['Username', 'Company name', 'Short name']
        print(_pretty_result(result, header))

    @staticmethod
    def _view_products():
        result = SQLCommands.custom_select_execute(
            query="""
            SELECT companies.company_name, product_types.product_type_name, products.product_name,
            products.product_cost, products.product_amount
            FROM products
            INNER JOIN product_types ON products.product_type_id = product_types.id
            INNER JOIN companies ON products.company_id = companies.id;
            """,
        )
        if not result:
            print('Ничего не нашли :(')

        header = ['company_name', 'product_type_name name', 'product_name', 'product_cost', 'product_amount']
        print(_pretty_result(result, header))

    @staticmethod
    def _view_my_loans():
        result = SQLCommands.custom_select_execute(
            query=f"""
            SELECT clients.last_name, clients.first_name, companies.company_name, products.product_name,
            products.product_cost, loans.loan_status, loans.loan_type, loans.order_amount,
            loans.credit_period, loans.credit_rate
            FROM loans
            INNER JOIN clients ON loans.client_id = clients.id
            INNER JOIN companies ON loans.company_id = companies.id
            INNER JOIN products ON loans.product_id = products.id
            WHERE client_id = {current_client.get().id};
            """,
        )
        if not result:
            print('Ничего не нашли :(')

        header = ['last_name', 'first_name', 'company_name', 'product_name', 'product_cost', 'loan_status', 'loan_type', 'order_amount', 'credit_period', 'credit_rate']
        print(_pretty_result(result, header))

    @staticmethod
    def _view_active_loans():
        result = SQLCommands.custom_select_execute(
            query="""
                SELECT clients.last_name, clients.first_name, companies.company_name, products.product_name,
                products.product_cost, loans.loan_status, loans.loan_type, loans.order_amount,
                loans.credit_period, loans.credit_rate
                FROM loans
                INNER JOIN clients ON loans.client_id = clients.id
                INNER JOIN companies ON loans.company_id = companies.id
                INNER JOIN products ON loans.product_id = products.id
                WHERE loan_status = 'created' OR loan_status = 'confirmed' OR loan_status = 'issued';
            """,
        )
        if not result:
            print('Ничего не нашли :(')

        header = ['last_name', 'first_name', 'company_name', 'product_name', 'product_cost', 'loan_status', 'loan_type', 'order_amount', 'credit_period', 'credit_rate']
        print(_pretty_result(result, header))

    @staticmethod
    def _view_my_documents():
        result = SQLCommands.custom_select_execute(
            query=f"""
                SELECT documents.current_type, citizenships.citizenship_name, documents.documents_number,
                documents.issue_date, documents.expiration_date
                FROM documents
                INNER JOIN citizenships ON documents.citizenship_id = citizenships.id
                INNER JOIN clients ON documents.id = clients.document_id
                WHERE clients.id = {current_client.get().id};
        """,
        )
        if not result:
            print('Ничего не нашли :(')

        header = ['current_type', 'citizenship_name', 'documents_number', 'issue_date', 'expiration_date']
        print(_pretty_result(result, header))


    _choices = {
        1: _fill_information_about_yourself,
        2: _view_companies,
        3: _view_products,
        4: _view_my_loans,
        5: _view_active_loans,
        6: _view_my_documents,
        7: _create_loan,
        0: LogoutMenu,
    }

    def menu(self):
        user = current_user.get()
        while True:
            print(CLIENT_MSG)
            choice = int(input('Ваш выбор: '))

            if choice not in self._choices:
                print(f'Нет выбора с пунктом {choice}\n')
                continue

            if choice not in (1, 0) and not user.is_active:
                print('Сначала необходимо добавить информацию о себе!')
                continue

            if choice == 0:
                return self._choices[choice]

            if not current_client.get():
                client = SQLCommands.select_one_execute(
                    table='clients',
                    where_str=f'user_id = {user.id}',
                    model=ClientModel,
                )

                current_client.set(client)

            self._choices[choice]()



class BaseMenu(ABCMenu):

    def menu(self):
        print(current_user.get())
        role = current_user.get().user_role
        print(BASE_MSG, f'ваша роль: {role}\n')

        if role == UserRoleEnum.client.name:
            return ClientMenu
        if role == UserRoleEnum.company.name:
            return BaseMenu
        if role == UserRoleEnum.staff.name:
            return BaseMenu
# ------------------------ END BASE ------------------------------

# ------------------------ START AUTH ------------------------------

class LoginMenu(ABCMenu):

    def menu(self):
        dict_model = UserModel().dict(include={'username', 'user_password'})
        print(LOGIN_MSG, [k for k in dict_model.keys()])

        while True:
            for k in dict_model.keys():
                dict_model[k] = input(f"Введите {k}: ")
            try:
                user = UserModel(**dict_model)
            except ValidationError as ex:
                print(f'\nВозникла ошибка:\n{ex}\n')
                if _is_agan():
                    return StartMenu
                continue

            user_from_db: Optional[UserModel] = SQLCommands.select_one_execute(
                table='users',
                where_str=f"username = '{user.username}'",
                model=UserModel,
            )

            if not user_from_db:
                print(f'Пользователь {user.username} не найден!')
                if _is_agan():
                    return StartMenu
                continue

            if user.user_password != user_from_db.user_password:
                print('Пароли не совпадают!')
                if _is_agan():
                    return StartMenu
                continue

            user_from_db.is_login = True
            current_user.set(user_from_db)
            print('Успешный вход!')
            break

        return BaseMenu


class RegisterMenu(ABCMenu):

    def menu(self):
        dict_model = UserModel().dict(exclude={'id', 'is_active', 'is_login'})
        print(REGISTER_MSG, [k for k in dict_model.keys()])

        while True:
            for k in dict_model.keys():
                dict_model[k] = input(f"Введите {k}: ")
            try:
                user = UserModel(**dict_model)
            except ValidationError as ex:
                print(f'\nВозникла ошибка:\n{ex}\n')
                if _is_agan():
                    return StartMenu
                continue

            user_from_db: Optional[UserModel] = SQLCommands.select_one_execute(
                table='users',
                where_str=f"username = '{user.username}'",
                model=UserModel,
            )

            if user_from_db:
                print(f'Пользователь {user.username} уже существует!')
                if input('Попробуем еще раз?\n1 - Да\n0 - Нет') == '0':
                    return StartMenu
                continue

            SQLCommands.insert_execute(
                table='users',
                dict_model=dict_model,
            )

            print('Успешная регистрация!')
            break

        return LoginMenu


class ExitMenu(ABCMenu):

    def menu(self):
        print('Досвидули, всего хорошего!')
        exit(0)

# ------------------------ END AUTH ------------------------------

# ------------------------ START START ------------------------------
class StartMenu(ABCMenu):

    _choices = {
        1: LoginMenu,
        2: RegisterMenu,
        0: ExitMenu,
    }

    def menu(self):
        print(START_APP_MESSAGE)

        while True:
            choice = int(input('Ваш выбор: '))

            if choice in self._choices:
                break

            print(f'Нет выбора с пунктом {choice}\n')
        return self._choices[choice]
# ------------------------ END START ------------------------------
