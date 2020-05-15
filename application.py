import os
import time
from datetime import datetime, timezone, timedelta
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    userid = session["user_id"]
    purchased = db.execute("SELECT * FROM purchase WHERE id=:uid", uid=userid)
    current_balance = db.execute("SELECT cash FROM users WHERE id=:uid",uid=userid)
    nrows = len(purchased)
    # print(purchased)
    dic = {}
    data = []
    temp_total = 0.0
    for row in purchased:
        # print(row)
        dic["symbol"] = row["symbol"]
        dic["name"] = row["name"]
        dic["shares"] = row["shares"]
        temp = lookup(row["symbol"])
        dic["price"] = usd(temp["price"])
        dic["total"] = usd(temp["price"] * row["shares"])
        print(type(temp["price"] * row["shares"]))
        temp_total = temp_total + float(temp["price"] * row["shares"])
        data.append(dic.copy())
        # print(data)
    # print(data)
    c_balance = usd(current_balance[0].get("cash"))
    # print(c_balance)
    grand_total = usd(temp_total + float(current_balance[0].get("cash")))
    return render_template("index.html", data=data, grand_total=grand_total, current_balance=c_balance)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        stock = lookup(request.form.get("symbol"))

        if stock == None:
            return apology("Symbol not found. Please re-check the symbol and try again!")

        shares = int(request.form.get("shares"))
        if not shares or int(shares) <= 0:
            return apology("Invalid shares. Please re-check and try again!")

        company_name = stock["name"]
        price = float(stock["price"])
        symbol = stock["symbol"]
        userid = session["user_id"]
        available_cash = (db.execute("SELECT cash FROM users WHERE id=:id", id = userid))[0].get("cash")
        total = shares*price
        if total > available_cash:
            return apology("Sorry! You do not have sufficient balance")
        else:
            check = (db.execute("SELECT symbol FROM purchase WHERE symbol=:symbol AND id=:uid", symbol=symbol, uid=userid))
            dt = datetime.now(timezone(timedelta(hours=6)))
            dt = dt.strftime("%d-%m-%Y %H:%M:%S")
            db.execute("INSERT INTO history (id, symbol, shares, price, time) VALUES (:userid, :symbol, :shares, :price, :time)", userid=userid, symbol=symbol,shares=shares,price=price, time=dt)
            db.execute("UPDATE users SET cash=:cash WHERE id=:uid", cash=available_cash-shares*price, uid=userid)

            # check = (db.execute("SELECT symbol FROM history WHERE symbol=:symbol", symbol=symbol))[0].get("symbol")
            print(len(check))
            if len(check) == 0:
                db.execute("INSERT INTO purchase (id, symbol, name, shares) VALUES (:userid, :symbol, :name, :shares)", userid=userid, symbol=symbol, name=company_name, shares=shares)
            else:
                exshares = int((db.execute("SELECT shares FROM purchase WHERE symbol=:symbol AND id=:uid", symbol=symbol,uid=userid))[0].get("shares"))
                # print(exshares+" "+type(exshares))
                extotal = float((db.execute("SELECT total FROM purchase WHERE symbol=:symbol AND id=:uid", symbol=symbol,uid=userid))[0].get("total"))
                db.execute("UPDATE purchase SET shares=:newshares WHERE symbol=:symbol AND id=:uid", newshares=shares+exshares, symbol=symbol, uid=userid)
            return render_template("bought.html", company_name=company_name, shares=shares, symbol=symbol, usd=usd(shares*price), balance=usd(available_cash-shares*price))





@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    userid = session["user_id"]
    history = db.execute("SELECT * FROM history WHERE id=:uid", uid=userid)
    dic = {}
    data = []
    for row in history:
        # print(row)
        dic["symbol"] = row["symbol"]
        dic["shares"] = row["shares"]
        dic["price"] = usd(row["price"])
        dic["time"] = row["time"]
        data.append(dic.copy())
        # print(data)
    return render_template("history.html", data=data)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = (request.form.get("symbol"))
        if not symbol:
            return apology("Please insert a symbol")
        if lookup(symbol) == None:
            return apology("Symbol went wrong. Please re-check the symbol and try again!")
        data = lookup(symbol)
        company_name = data["name"]
        price = usd(data["price"])
        symbol = data["symbol"]
        if not company_name or not price or not symbol:
            return apology("no symbol found!")
        return render_template("quoted.html", company_name=company_name, usd=price, symbol=symbol)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached via GET
    if request.method == "GET":
        return render_template("register.html")
    # return apology("TODO")
    #User reached via POST
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        cpassword = request.form.get("cpassword")

        # Check whether both the passwords match
        if(password != cpassword):
            message = "password didn't match"
            # print("password didn't match")
            return render_template("register.html", message=message)

        # check if user name already exists
        usr = db.execute("SELECT username FROM users WHERE username = :username", username=username)
        if len(usr) != 0:
            return render_template("register.html", message="Username already exists. Please try a different one!")

        #Hash the password
        hashh = generate_password_hash(password)
        # print(hashh)

        # Create a new user
        db.execute("INSERT INTO users(username, hash) VALUES(:username, :hashh)", username=username, hashh=hashh)
        return render_template("register.html", success="Registration successful!")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    userid = session["user_id"]
    if request.method == "GET":
        symbol = db.execute("SELECT symbol FROM purchase WHERE id=:uid",uid=userid)
        # print(symbol)
        symbols = []
        for s in symbol:
            temp = s["symbol"]
            symbols.append(temp)
        # print(symbols)
        return render_template("sell.html", symbols=symbols)
    else:
        symbol_entry = request.form.get("symbol")
        shares_entry = int(request.form.get("shares"))
        if not symbol_entry or not shares_entry:
            return apology("Please select both symbol and shares")

        data = db.execute("SELECT symbol, shares FROM purchase WHERE id=:uid",uid=userid)
        share_check = 0

        for s in data:
            if(s["symbol"] == symbol_entry):
                share_check = s["shares"]
        # print(share_check)
        if shares_entry > share_check:
            return apology("You don't have this many shares of this company")

        current_cash = (db.execute("SELECT cash FROM users WHERE id=:uid", uid=userid))[0].get("cash")
        query = lookup(symbol_entry)
        share_price = query["price"]
        sold_price = share_price * shares_entry

        db.execute("UPDATE users SET cash=:sold WHERE id=:uid",sold=sold_price+current_cash, uid=userid)
        if shares_entry == share_check:
            db.execute("DELETE FROM purchase WHERE symbol=:symbol AND id=:uid", symbol=symbol_entry, uid=userid)
        else:
            db.execute("UPDATE purchase SET shares=:shares WHERE symbol=:symbol AND id=:uid",shares=share_check-shares_entry,symbol=symbol_entry, uid=userid)

        nshare = -shares_entry
        dt = datetime.now(timezone(timedelta(hours=6)))
        dt = dt.strftime("%d-%m-%Y %H:%M:%S")
        db.execute("INSERT INTO history (id, symbol, shares, price, time) VALUES (:userid, :symbol, :shares, :price, :time)", userid=userid, symbol=symbol_entry,shares=nshare,price=share_price, time=dt)
        return render_template("sell.html", message="Sold!")
        print(data)

@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    """add more cash to the user account"""
    userid = session["user_id"]
    if request.method == "GET":
        return render_template("add_cash.html")
    else:
        cash = int(request.form.get("cash"))
        current_balance = (db.execute("SELECT cash FROM users WHERE id=:uid", uid=userid))[0].get("cash")
        db.execute("UPDATE users SET cash=:cash WHERE id=:uid", cash=cash+current_balance, uid=userid)
        success = "$"+str(cash)+" successfully added to your account"
        message = "Your current balance is $"+str(cash+current_balance)
        return render_template("add_cash.html", success=success, message=message)



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
