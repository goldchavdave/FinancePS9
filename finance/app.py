import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # get all stocks user has from stocks. Recieve dict of symbols and shares
    allStocks = db.execute("SELECT symbol, shares FROM stocks WHERE id =: user", user = session["user_id"])

    # save symbols and shares
    symbol = allStocks["symbol"]
    share = allStocks["shares"]
    # look up each symbol to get current stock price
    stock = lookup(symbol)
    # save indiv stock price
    iStock = stock["price"]
    # calc total stock price (tsp)
    tsp = iStock * share
    # save coName
    name = stock["name"]

    # user curr cash amount
    cash = db.execute("SELECT cash FROM users WHERE id =: user", user = session["user_id"])
    # calc total user amt: cash and stocks
    tAmount = tsp + cash

    return render_template("index.html",
    stocks = [{"symbol": symbol, "name": name, "shares": share, "price": iStock, "total": tsp}])

@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    """Add money into user account"""
    if request.method == "POST":
        # make sure an amount is entered
        if not request.form.get("amount"):
            return apology("Please enter an amount", 403)
        # get username and cash from users
        info = db.execute("SELECT cash, username FROM users WHERE id =: id", id = session["user_id"])
        username = info["username"]
        curCash = info["cash"]
        # add amount to cash and save in amount
        amount = float(request.form.get("amount")) + curCash
        # update cash in users to reflect the added amount
        db.execute("UPDATE users SET cash =: cash WHERE username =: username", cash = amount, username = username)

    else:
        return render_template("account.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        #check for correct usage of symbol; save symbol
        if not request.form.get("symbol"):
            return apology("Please enter a symbol", 403)
        elif lookup(request.form.get("symbol")) == None:
            return apology("Please enter a valid symbol", 403)
        else:
            symbolD = lookup(request.form.get("symbol"))

        # check for valid shares entry
        if request.form.get("shares") < 1 or not request.form.get("shares"):
            return apology("Please enter 1 or more shares you would like to purchase", 403)
        else:
            shares = int(request.form.get("shares"))

        # save symbol
        symbol = request.form.get("symbol")

        # save the price of share
        stockP = symbolD["price"]
        # calc price of stock * amount of shares
        price = float(stockP) * shares
        buyer = session["user_id"]

        # get cash amount of user
        cash = db.execute("SELECT cash FROM users WHERE id =: buyer", buyer = buyer)
        # check if buyer has enough cash to purchase shares
        if price <= cash[0]["cash"]:
            # create a new row with the data of the purchase in purchase
            db.execute("INSERT INTO transactions (id, trans, date, stock, shares, price) VALUES (?, 'Bought', NOW(), ?, ?, ?)", buyer, symbol, shares, price)
            # add purchase into stock table
            # if buyer does not yet have any of these stocks
            if db.execute("SELECT symbol FROM stocks WHERE id =: id", id = buyer) != symbol:
                db.execute("INSERT INTO stocks (id, date, stock, shares, price) VALUES (?, NOW(), ?, ?, ?)", buyer, symbol, shares, stockP)
            # if buyer already purchased at least 1 of these stocks, update share amount
            else:
                curShare = db.execute("SELECT shares FROM stocks WHERE id =: id AND stock =: symbol", id = buyer, symbol = symbol)
                current = shares + curShare
                db.execute("UPDATE stocks SET shares =: shares, price =: price WHERE id =: id", shares = current, price = stockP, id = buyer)

            # update cash in users to reflect the purchase
            db.execute("UPDATE users SET cash =: cash WHERE id =: buyer", cash = cash[0]["cash"] - price, buyer = buyer)
        else:
            return apology("Not enough funds", 403)

    # if method is GET
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # get transactions from transactions
    hsitory = db.execute("SELECT trans, symbol, shares, price, date FROM transactions WHERE id =: id", id = session["user_id"])
    type = history["trans"]
    symbol = history["symbol"]
    shares = history["shares"]
    price = history["price"]
    date = history["date"]

    return render_template("history.html",
    trans = [{"type": type, "symbol": symbol, "shares": shares, "price": price, "date": date}])


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
        rows = db.execute("SELECT * FROM users WHERE username =: user", user = request.form.get("username"))

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
    # User reached route via POST
    if request.method == "POST" :
        quote = lookup(request.form.get("symbol"))
        if quote is None :
            return apology("Please enter a correct symbol", 403)
        else:
            return render_template("quoted.html")

    # User reached route via GET
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
     # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure user verified password
        elif not request.form.get("confirmation"):
            return apology("must verify password", 400)

        # Ensure password and password verification match
        elif not request.form.get("password") == request.form.get("confirmation"):
            return apology("passwords don't match", 400)

        # Query database for username
        username = request.form.get("username")
        rows = db.execute("SELECT * FROM users WHERE username =: user", user = username)

        # Check if username is already in use
        if len(rows) > 0 :
            return apology("Username taken", 400)

        passwordHash = generate_password_hash(request.form.get("password"))

        # insert new user data into table
        new = db.execute("INSERT INTO users (username, hash) VALUES (:user, :hash)", user = username, hash = passwordHash)

        # Remember which user has logged in
        session["user_id"] = new[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        # error check for blank fields
        if not request.form.get("shares"):
            return apology("Please enter the number of share you would like to sell", 403)
        if not request.form.get("symbol"):
            return apology("Please select a stock to sell", 403)

        # save symbol and shares as var
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # calcualte profit from sale
        stock = lookup(request.form.get("symbol"))
        price = stock["price"]
        profit = price * request.form.get("shares")

        seller = session["user_id"]
        # get current cash and add profit for new user amount
        cash = db.execute("SELECT cash FROM users WHERE id =: user", id = seller)
        accAmount = cash + profit

        # update users cash
        db.execute("UPDATE users SET cash =: profit WHERE id =: user", profit = accAmount, user = seller)

        # add entry into sell
        db.execute("INSERT INTO transactions (id, trans, date, stock, shares, price) VALUES (?, 'Sold', NOW(), ?, ?, ?)", seller, symbol, shares, price)

        #update stocks to reflect sale
        curShare = db.execute("SELECT shares FROM stocks WHERE id =: id AND stock =: symbol", id = seller, symbol = symbol)
        current = curShare - shares
        db.execute("UPDATE stocks SET shares =: shares, price =: price WHERE id =: id", shares = current, price = price, id = seller)

        # if shares in this stock = 0, delete stock from stocks
        if db.execute("SELECT shares FROM stocks WHERE id =: id AND stock =: stock", id = seller, stock = symbol) == 0:
            db.execute("DELETE FROM stocks WHERE id =: id AND stock =: stock", id = seller, stock = symbol)

    else:
        return render_template("sell.html")
