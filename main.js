function visibility() {
    if (document.hidden) {
        let visibility = {
            uuid: uuid,
            type: "hidden"
        };
        socket.send(JSON.stringify(visibility));
        console.log("hidden");
    }else{
        if (socket.readyState == WebSocket.CLOSED) {
            socketInit();
        }
        let visibility = {
            uuid: uuid,
            type: "visible"
        };
        socket.send(JSON.stringify(visibility));
        console.log("visible");
    }
}

function socketInit() {
    console.log("socket init");

    socket = new WebSocket("ws://makedrink.me:8765");

    socket.onopen = function () {
        console.log("socket open");

        let query = {
            uuid: uuid,
            type: "query"
        };
        socket.send(JSON.stringify(query));

        document.onvisibilitychange = visibility;
        visibility();

        socketAttempts = 0;

        if (!socketConnected) {
            socketConnected = true;
            statusConnection.textContent = "Connected";
            statusConnection.style.color = "var(--color-pos)";
        }
    }

    socket.onclose = function () {
        console.log("socket close");
        if (socketConnected) {
            socketConnected = false;
            statusConnection.textContent = "Disconnected";
            statusConnection.style.color = "var(--color-neg)";
        }
        let delay = 3000;
        if (socketAttempts == 0) {
            delay = 0;
        }
        setTimeout(() => {
            if (socket.readyState == WebSocket.CLOSED) {
                socketInit();
            }
        }, delay);

        socketAttempts++;
    }

    socket.onerror = function () {
        console.log("socket error");
        socket.close();
    }

    socket.onmessage = function (event) {
        console.log("socket message");
        let msg = JSON.parse(event.data);
        console.log(msg);
        if (msg.drinks) {

            drinks = msg.drinks;
            ingredients = msg.ingredients;

            for (let name in drinks) {
                if (drinkElems[name] == null) {

                    drinkElems[name] = new DrinkItem(name, 'drinks');
                    lists['drinks'].append(drinkElems[name]);
                }

                drinkElems[name].updateEmpty();
            }

            for (let name in ingredients) {
                if (ingredientElems[name] == null) {

                    ingredientElems[name] = new IngredientItem(name);
                    lists['ingredients'].append(ingredientElems[name]);
                }

                ingredientElems[name].updateEmpty();
            }

            drinkElems['Custom Drink'].updateEmpty();

            if (detailElems['drinks'].expanded) {
                detailElems['drinks'].updateEmpty();
            }
            if (detailElems['ingredients'].expanded) {
                detailElems['ingredients'].updateEmpty();
            }
        }
        if (msg.status) {

            if (msg.status.userState != userState) {
                userState = msg.status.userState;
                if (detailElems['drinks'].expanded) {
                    detailElems['drinks'].updateButtons();
                }
                if (detailElems['ingredients'].expanded) {
                    detailElems['ingredients'].updateButtons();
                }
                clearInterval(statusTimer);

                if (userState == "FRONTLINE") {
                    //msg.status.timer += Date.now()/1000;
                    statusBase.classList.remove("bar-progress");
                    statusBase.classList.add("bar-timer");
                    statusTimer = setInterval(() => {
                        statusTime -= 1;
                        if (statusTime < 0) {
                            clearInterval(statusTimer);
                        } else {
                            statusBase.style.transform = "scaleX(" + statusTime * 5 + "%)";
                        }
                    }, 1000);

                    statusButton.classList.remove("grey", "cancel");
                    statusButton.classList.add("pour");
                    statusButton.textContent = "Pour";
                } else if (userState == "POURING") {
                    statusBase.classList.remove("bar-timer");
                    statusBase.classList.add("bar-progress");

                    statusButton.classList.remove("grey", "pour");
                    statusButton.classList.add("cancel");
                    statusButton.textContent = "Cancel";
                } else {
                    statusBase.style.transform = "scaleX(0)";

                    statusButton.classList.add("grey");
                    statusButton.classList.remove("cancel", "pour");
                    statusButton.textContent = "Pour";
                }
            }
            if (userState == "FRONTLINE") {
                statusTime = msg.status.timer;
                statusBase.style.transform = "scaleX(" + statusTime * 5 + "%)";
            }
            if (userState == "POURING") {
                statusBase.style.transform = "scaleX(" + msg.status.progress + "%)";
            }

            if (userState == "INLINE" || userState == "FRONTLINE" || userState == "POURING") {
                statusQueue.textContent = "Queue: " + msg.status.position + "/" + msg.status.size;
                statusDrink.textContent = queuedDrink.name;
                statusOutlet.textContent = queuedDrink.outlet;
            } else {
                statusQueue.textContent = "Queue: " + msg.status.size;
                statusDrink.textContent = "";
                statusOutlet.textContent = "";
            }

            statusState.textContent = msg.status.makerState;
        }
        if (msg.user) {
            userDrinks.textContent = decimal(msg.user.drinks, 1);
            userBAC.textContent = decimal(msg.user.bac, 3);

            userNameInput.value = msg.user.name;
            userWeightInput.value = msg.user.weight;

            if (msg.user.name != "") {
                drinkElems['Custom Drink'].nameElem.textContent = msg.user.name + "'s Drink";
            } else {
                drinkElems['Custom Drink'].nameElem.textContent = "Custom Drink";
            }


            userSex = msg.user.sex;
            if (userSex == "male") {
                userFemaleButton.classList.remove("active");
                userMaleButton.classList.add("active");
            } else if (userSex == "female") {
                userMaleButton.classList.remove("active");
                userFemaleButton.classList.add("active");
            }
        }
    };
}

class DrinkItem extends HTMLElement {
    constructor(name, page) {
        super();

        this.appendChild(templateDrinkItem.content.cloneNode(true));

        this.name = name;
        if (drinks[name] != null) {
            this.ingredients = drinks[name];
        } else {
            this.ingredients = {};
        }

        this.empty = false;
        this.page = page;

        this.nameElem = this.querySelector(".drink-name");
        this.nameElem.textContent = this.name;

        this.ingredientsElem = this.querySelector(".ingredient-summary");
        this.ingredientsSummary = "";

        this.updateIngredients();

        this.onclick = function () {
            event.stopPropagation();
            this.expandDetail(this.name);
        };
    }

    updateEmpty() {
        let empty = false;
        let volume = 0;
        for (let ingredient in this.ingredients) {
            volume += this.ingredients[ingredient];
            if (ingredients[ingredient].empty) {
                empty = true;
                break;
            }
        }
        if (volume == 0) {
            empty = true;
        }

        if (empty && !this.empty) {
            this.classList.add("drink-empty");
            this.empty = empty;
        } else if (!empty && this.empty) {
            this.classList.remove("drink-empty");
            this.empty = empty;
        }
    }

    updateIngredients() {
        let ingredientSummary = "";
        for (let ingredient in this.ingredients) {
            ingredientSummary += ingredient + ", "
        }

        if (ingredientSummary != this.ingredientSummary) {
            this.ingredientSummary = ingredientSummary
            this.ingredientsElem.textContent = this.ingredientSummary;
        }
    }

    expandDetail() {
        if (detailElems[this.page].expanded) {
            return;
        }
        detailElems[this.page].expanded = true;

        detailElems[this.page].name = this.name;

        detailElems[this.page].alcoholSlider.value = 1;
        detailElems[this.page].nonalcoholSlider.value = 1;
        detailElems[this.page].updateBody();
        detailElems[this.page].updateEmpty();

        detailElems[this.page].nameElem.textContent = this.nameElem.textContent;
        detailElems[this.page].ingredientBoxElem.style.height = (3.5 * Object.keys(this.ingredients).length) + "vh";

        detailElems[this.page].bodyElem.classList.remove("shrunk");

        let y = -this.getBoundingClientRect().top + pages[this.page].getBoundingClientRect().top + bigVH;

        pages[this.page].classList.add("noscroll");
        lists[this.page].classList.add("notouch", "transparent");
        this.classList.add("notouch", "transparent");

        detailElems[this.page].style.top = this.offsetTop - bigVH + "px";
        detailElems[this.page].classList.remove("notouch", "transparent");
        detailElems[this.page].style.transform = "translateY(" + y + "px)";
    }
}
customElements.define('drink-item', DrinkItem);


class DrinkDetail extends HTMLElement {
    constructor() {
        super();

        var templateDrinkDetail = document.getElementById("template-drink-detail").content;
        this.appendChild(templateDrinkDetail.cloneNode(true));

        this.expanded = false;
        this.empty = false;
        this.same = false;

        this.page = this.getAttribute('page');

        this.nameElem = this.querySelector('.drink-name');
        this.itemElem = this.querySelector('.drink-item');

        this.bodyElem = this.querySelector('.drink-detail-body');
        this.ingredientBoxElem = this.querySelector('.ingredient-box');

        this.ingredients = {};
        this.ingredientsElem = new Array(40);
        var templateIngredientAmount = document.getElementById("template-ingredient-amount").content;
        for (var i = 0; i < 40; i++) {
            let item = templateIngredientAmount.cloneNode(true).children[0];
            this.ingredientsElem[i] = item;
            this.ingredientBoxElem.append(item);
        }

        this.volume = this.querySelector('.volume-label');
        this.alcohol = this.querySelector('.alcohol-label');
        this.abv = this.querySelector('.abv-label');

        this.alcoholMult = this.querySelector('.alcohol-mult');
        this.alcoholSlider = this.querySelector('.alcohol-slider');
        this.alcoholSlider.oninput = this.updateBody.bind(this);
        this.alcoholSlider.addEventListener('touchstart', this.sliderStart, { passive: true });
        this.alcoholSlider.addEventListener('touchend', this.sliderStop, { passive: true });
        this.alcoholSlider.addEventListener('touchcancel', this.sliderStop, { passive: true });

        this.nonalcoholMult = this.querySelector('.nonalcohol-mult');
        this.nonalcoholSlider = this.querySelector('.nonalcohol-slider');
        this.nonalcoholSlider.oninput = this.updateBody.bind(this);
        this.nonalcoholSlider.addEventListener('touchstart', this.sliderStart, { passive: true });
        this.nonalcoholSlider.addEventListener('touchend', this.sliderStop, { passive: true });
        this.nonalcoholSlider.addEventListener('touchcancel', this.sliderStop, { passive: true });

        this.tubButton = this.querySelector('.tub-button');
        this.basementButton = this.querySelector('.basement-button');

        this.tubButton.onclick = () => {
            this.detailClick('hottub');
        }
        this.basementButton.onclick = () => {
            this.detailClick('basement');
        }

        this.onclick = () => {
            event.stopPropagation();
            this.collapseDetail();
        };
    }

    sliderStart() {
        pageView.classList.add('noscroll');
    }

    sliderStop() {
        pageView.classList.remove('noscroll');
    }

    addQueue() {
        let msg = {
            uuid: uuid,
            type: "queue"
        };
        socket.send(JSON.stringify(msg));
    }

    removeQueue() {
        let msg = {
            uuid: uuid,
            type: "remove"
        };
        socket.send(JSON.stringify(msg));
    }

    changeQueue(outlet) {
        queuedDrink.name = this.name;
        queuedDrink.ingredients = {};
        for (let ingredient in this.ingredients) {
            queuedDrink.ingredients[ingredient] = this.ingredients[ingredient];
        }
        queuedDrink.outlet = outlet;
        if (userState == "INLINE" || userState == "FRONTLINE" || userState == "POURING") {
            statusDrink.textContent = queuedDrink.name;
            statusOutlet.textContent = queuedDrink.outlet;
        }
        this.same = true;
    }

    updateBody() {
        this.updateInfo();
        this.updateButtons();
    }

    updateInfo() {
        let alcoholMult = this.alcoholSlider.value;
        let nonalcoholMult = this.nonalcoholSlider.value;
        let totalVolume = 0;
        let alcoholVolume = 0;
        this.same = true;
        if (this.name != queuedDrink.name) {
            this.same = false;
        }
        let i = 0;
        this.ingredients = {};
        for (let ingredient in drinkElems[this.name].ingredients) {
            let abv = ingredients[ingredient].abv;
            let volume = 0;
            if (abv > 0) {
                volume = drinkElems[this.name].ingredients[ingredient] * alcoholMult;
                alcoholVolume += volume * abv;
            } else {
                volume = drinkElems[this.name].ingredients[ingredient] * nonalcoholMult;
            }
            this.ingredients[ingredient] = volume;
            if (this.ingredients[ingredient] != queuedDrink.ingredients[ingredient]) {
                this.same = false;
            }
            totalVolume += volume;
            if (ingredients[ingredient].empty) {
                this.ingredientsElem[i].textContent = ingredient + ": " + decimal(volume, 2) + " oz (EMPTY)";
            } else {
                this.ingredientsElem[i].textContent = ingredient + ": " + decimal(volume, 2) + " oz";
            }
            i++;
        }

        this.volume.textContent = "total: " + decimal(totalVolume, 2) + " oz";
        this.alcohol.textContent = "drinks: " + decimal(alcoholVolume / 0.6, 1);
        if (totalVolume > 0) {
            this.abv.textContent = "ABV: " + decimal(alcoholVolume * 100 / totalVolume, 1) + "%";
        } else {
            this.abv.textContent = "ABV: 0%";
        }

        this.alcoholMult.textContent = "Alcohol: " + alcoholMult + "x";
        this.nonalcoholMult.textContent = "Non-alcohol: " + nonalcoholMult + "x";
    }

    updateButtons() {
        if (userState == "NOLINE" || userState == "OUTLINE" || userState == "POURING") {
            this.basementButton.textContent = "Add Basement";
            this.tubButton.textContent = "Add Hot Tub";
        }
        else if (userState == "INLINE" || userState == "FRONTLINE") {
            if (this.same && queuedDrink.outlet == 'basement') {
                this.basementButton.textContent = "Remove Basement";
                this.tubButton.textContent = "Change Hot Tub";
            } else if (this.same && queuedDrink.outlet == 'hottub') {
                this.basementButton.textContent = "Change Basement";
                this.tubButton.textContent = "Remove Hot Tub";
            } else {
                this.basementButton.textContent = "Change Basement";
                this.tubButton.textContent = "Change Hot Tub";
            }
        }
    }

    detailClick(outlet) {
        event.stopPropagation();
        if (this.empty) {
            return;
        }
        if (userState == "NOLINE" || userState == "OUTLINE" || userState == "POURING") {
            this.changeQueue(outlet);
            this.addQueue();
        }
        else if (userState == "INLINE" || userState == "FRONTLINE") {
            if (this.same && queuedDrink.outlet == outlet) {
                this.removeQueue();
            } else {
                this.changeQueue(outlet);
                this.updateButtons();
            }
        }
    }

    collapseDetail() {
        let name = this.name;

        this.style.transform = "translateY(0px)";
        this.classList.add("notouch");
        this.bodyElem.classList.add("shrunk");

        pages[this.page].classList.remove("noscroll");
        lists[this.page].classList.remove("notouch", "transparent");

        setTimeout(() => {
            drinkElems[name].classList.remove("notouch", "transparent");
            this.classList.add("transparent");
            this.style.top = "0px";
            this.expanded = false;
        }, 200);
    }

    updateEmpty() {
        if (drinkElems[this.name].empty && !this.empty) {
            this.classList.add("drink-empty");
            this.empty = drinkElems[this.name].empty;
        } else if (!drinkElems[this.name].empty && this.empty) {
            this.classList.remove("drink-empty");
            this.empty = drinkElems[this.name].empty;
        }
    }
}
customElements.define('drink-detail', DrinkDetail);


class IngredientItem extends HTMLElement {
    constructor(name) {
        super();

        this.appendChild(templateIngredientItem.content.cloneNode(true));

        this.name = name;
        this.empty = false;
        this.volume = 0;

        this.nameElem = this.querySelector(".ingredient-name");
        this.nameElem.textContent = this.name;

        this.plus = this.querySelector(".ingredient-plus");
        this.minus = this.querySelector(".ingredient-minus");

        this.volumeElem = this.querySelector(".ingredient-volume");
        this.volumeElem.textContent = this.volume + " oz";

        this.plus.onclick = this.ingredientPlus.bind(this);
        this.minus.onclick = this.ingredientMinus.bind(this);

        // this.plus.addEventListener('touchstart', ()=>{
        //     this.ingredientPlus();
        //     clearInterval(this.buttonInterval);
        //     this.buttonInterval = setInterval(()=>{
        //         this.ingredientPlus();
        //     }, 100);
        // }, { passive: true });
        // this.plus.addEventListener('touchend', ()=>{
        //     clearInterval(this.buttonInterval);
        // }, { passive: true });
        // this.plus.addEventListener('touchcancel', ()=>{
        //     clearInterval(this.buttonInterval);
        // }, { passive: true });

        // this.minus.addEventListener('touchstart', ()=>{
        //     this.ingredientMinus();
        //     clearInterval(this.buttonInterval);
        //     this.buttonInterval = setInterval(()=>{
        //         this.ingredientMinus();
        //     }, 100);
        // }, { passive: true });
        // this.minus.addEventListener('touchend', ()=>{
        //     clearInterval(this.buttonInterval);
        // }, { passive: true });
        // this.minus.addEventListener('touchcancel', ()=>{
        //     clearInterval(this.buttonInterval);
        // }, { passive: true });

        // this.buttonInterval = null;
    }

    updateEmpty() {
        if (ingredients[this.name].empty && !this.empty) {
            this.classList.add("drink-empty");
            this.empty = ingredients[this.name].empty;
        } else if (!ingredients[this.name].empty && this.empty) {
            this.classList.remove("drink-empty");
            this.empty = ingredients[this.name].empty;
        }
    }

    ingredientPlus() {
        this.ingredientChange(Math.min(this.volume + 0.1, 8));
    }

    ingredientMinus() {
        this.ingredientChange(Math.max(this.volume - 0.1, 0));
    }

    ingredientChange(volume) {
        if (!ingredients[this.name].empty) {
            this.volume = decimal(volume, 1);
        } else {
            this.volume = 0;
        }
        this.volumeElem.textContent = this.volume + " oz";

        if (this.volume == 0) {
            delete drinkElems['Custom Drink'].ingredients[this.name];
        } else {
            drinkElems['Custom Drink'].ingredients[this.name] = this.volume;
        }

        drinkElems['Custom Drink'].updateEmpty();
        drinkElems['Custom Drink'].updateIngredients();
    }

    updateCustomDrink() {
        let drink
        for (let name in ingredients) {
            if (this.volume > 0) {

            }
        }
    }
}
customElements.define('ingredient-item', IngredientItem);



function statusClick() {
    if (userState == "FRONTLINE") {
        let msg = {
            uuid: uuid,
            type: "pour",
            name: queuedDrink.name,
            ingredients: queuedDrink.ingredients,
            outlet: queuedDrink.outlet
        };
        socket.send(JSON.stringify(msg));
    } else if (userState == "POURING") {
        let msg = {
            uuid: uuid,
            type: "cancel"
        };
        socket.send(JSON.stringify(msg));
    }
}

function decimal(num, place) {
    return Math.round(num * Math.pow(10, place)) / Math.pow(10, place)
}

function setPage(page) {
    pages[page].scrollIntoView({ behavior: "smooth" });
}

function hue2rgb(p, q, t) {
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
}


class ThemeButton extends HTMLElement {
    constructor(theme) {
        super();

        //let templateColorButton = document.getElementById("template-theme-button").content;
        //this.appendChild(templateDrinkItem.content.cloneNode(true));

        this.theme = theme;

        //this.nameElem = this.querySelector(".theme-button");
        this.textContent = this.theme;

        this.colors = [];

        // let gradient = "";
        // for (let x in themes[this.theme].css){
        //     gradient += themes[this.theme].css[x] + ", ";
        // }
        // gradient = gradient.substr(0, gradient.length-2);
        // console.log(gradient);

        // this.style.backgroundImage = "linear-gradient(to right, " + gradient + ")";

        this.onclick = () => {
            setTheme(this.theme, true);
        };
    }
}
customElements.define('theme-button', ThemeButton);

/////////////////////////////////////////

var drinksTab = document.getElementById("drinks-tab");
drinksTab.onclick = () => { setPage('drinks') };

var ingredientsTab = document.getElementById("ingredients-tab");
ingredientsTab.onclick = () => { setPage('ingredients') };

var userTab = document.getElementById("user-tab");
userTab.onclick = () => { setPage('user') };

var pageView = document.getElementById("page-view");

var tabBar = document.getElementById("tab-bar");

var drinks = {};
var ingredients = {};

var pages = {};
var lists = {};

const flareCount = 80;
const flareSize = 1.5;
const flareSpeed = 0.2;

const buffer = new ArrayBuffer(flareCount * 28);
const dv = new DataView(buffer);

/////////////////////////////////////////

pages['drinks'] = document.getElementById("drinks-page");
lists['drinks'] = document.getElementById("drink-list");
var drinkElems = {};

var templateDrinkItem = document.getElementById("template-drink-item");
var templateIngredientItem = document.getElementById("template-ingredient-item");

var detailElems = {};
detailElems['drinks'] = document.getElementById("detail-drinks");
detailElems['ingredients'] = document.getElementById("detail-ingredients");

var userState = "";
var makerState = "";

/////////////////////////////////////////

pages['ingredients'] = document.getElementById("ingredients-page");
lists['ingredients'] = document.getElementById("ingredient-list");
var ingredientElems = {};

var ingredientTemplate = document.getElementById("template-ingredient-item");

drinkElems['Custom Drink'] = new DrinkItem('Custom Drink', 'ingredients');
pages['ingredients'].append(drinkElems['Custom Drink']);

/////////////////////////////////////////

pages['user'] = document.getElementById("user-page");

var userNameInput = document.getElementById("user-name-input");
var userWeightInput = document.getElementById("user-weight-input");
var userMaleButton = document.getElementById("user-male-button");
var userFemaleButton = document.getElementById("user-female-button");

var userDrinks = document.getElementById("user-drinks-value");
var userBAC = document.getElementById("user-bac-value");

userMaleButton.onclick = function () {
    userSex = "male";
    userFemaleButton.classList.remove("active");
    userMaleButton.classList.add("active");
}

userFemaleButton.onclick = function () {
    userSex = "female";
    userMaleButton.classList.remove("active");
    userFemaleButton.classList.add("active");
}

var userUpdate = document.getElementById("user-update");
userUpdate.onclick = function () {
    var msg = {
        uuid: uuid,
        type: "user",
        name: userNameInput.value,
        weight: userWeightInput.value,
        sex: userSex
    };
    socket.send(JSON.stringify(msg));
}

var userSex = "";

const themes = {
    vapor: {
        css: {
            "--color-background": "hsl(170, 100%, 0%)",
            "--color-panel": "hsl(0, 0%, 100%, 10%)",
            "--color-pos": "hsl(170, 100%, 30%)",
            "--color-neg": "hsl(320, 100%, 30%)",
            "--color-a": "hsl(320, 100%, 40%)",
            "--color-b": "hsl(200, 100%, 30%)",
            "--color-c": "hsl(290, 100%, 30%)",
        },
        webgl: [
            [0, 102, 85],
            [0, 34, 102],
            [51, 0, 102],
            [102, 0, 68],
        ]
    },
    /*
    sunset: {
        css:{
            "--color-background": "hsl(240, 100%, 20%)",
            "--color-panel": "hsl(0, 0%, 100%, 10%)",
            "--color-pos": "hsl(50, 100%, 30%)",
            "--color-neg": "hsl(270, 100%, 30%)",
            "--color-a": "hsl(270, 100%, 40%)",
            "--color-b": "hsl(320, 100%, 30%)",
            "--color-c": "hsl(0, 100%, 30%)",
        },
        webgl: [
            [51, 0, 102],
            [102, 0, 75],
            [102, 9, 0],
            [102, 85, 0],
        ]
    },
    
    starfield: {
        css:{
            "--color-background": "hsl(200, 100%, 20%)",
            "--color-panel": "hsl(0, 0%, 100%, 10%)",
            "--color-pos": "hsl(50, 100%, 30%)",
            "--color-neg": "hsl(0, 100%, 30%)",
            "--color-a": "hsl(12, 100%, 40%)",
            "--color-b": "hsl(24, 100%, 30%)",
            "--color-c": "hsl(36, 100%, 30%)",
        },
        webgl: [
            [0, 51, 102],
            [102, 0, 0],
            [102, 43, 0],
            [102, 85, 0],
        ]
    },
    // starfield - red, yellow, orange, blue
    // fog - grayscale
    // sunset - red, orange, purple, blue
    sunset: {
        css:{
            "--color-background": "hsl(240, 100%, 20%)",
            "--color-panel": "hsl(0, 0%, 100%, 10%)",
            "--color-pos": "hsl(50, 100%, 30%)",
            "--color-neg": "hsl(270, 100%, 30%)",
            "--color-a": "hsl(270, 100%, 40%)",
            "--color-b": "hsl(320, 100%, 30%)",
            "--color-c": "hsl(0, 100%, 30%)",
        },
        webgl: [
            [51, 0, 102],
            [102, 0, 75],
            [102, 9, 0],
            [102, 85, 0],
        ]
    },
    */
    fog: {
        css: {
            "--color-background": "hsl(0, 0%, 0%)",
            "--color-panel": "hsl(0, 0%, 100%, 10%)",
            "--color-pos": "hsl(0, 0%, 40%)",
            "--color-neg": "hsl(0, 0%, 10%)",
            "--color-a": "hsl(0, 0%, 20%)",
            "--color-b": "hsl(0, 0%, 30%)",
            "--color-c": "hsl(0, 0%, 40%)",
        },
        webgl: [
            [102, 102, 102],
            [77, 77, 77],
            [51, 51, 51],
            [26, 26, 26],
        ]
    },
};


const themeButtons = {};

let themeList = document.getElementById('user-theme-list');
for (let x in themes) {
    themeButtons[x] = new ThemeButton(x);
    themeList.append(themeButtons[x]);
}

function setTheme(x, store) {
    for (let i in themeButtons) {
        themeButtons[i].classList.remove('active');
    }
    themeButtons[x].classList.add('active');

    for (let prop in themes[x].css) {
        document.documentElement.style.setProperty(prop, themes[x].css[prop]);
    }

    for (let i = 0; i < flareCount; i++) {
        //let num = Math.floor(Math.random() * themes[x].webgl.length);
        let num = i % themes[x].webgl.length;
        dv.setFloat32(28 * i + 16, themes[x].webgl[num][0] / 255, true);
        dv.setFloat32(28 * i + 20, themes[x].webgl[num][1] / 255, true);
        dv.setFloat32(28 * i + 24, themes[x].webgl[num][2] / 255, true);
    }

    gl.bufferData(gl.ARRAY_BUFFER, buffer, gl.STATIC_DRAW);

    if (store) {
        localStorage.setItem('theme', x);
    }


}

var theme = localStorage.getItem('theme');
if (theme == null) {
    theme = "vapor";
    localStorage.setItem('theme', theme);
}
//setColorPalette(colorPalette, false);

////////////////////////////////////////////////////////////////

var statusBase = document.getElementById("status-bar");

var statusQueue = document.getElementById("status-queue");
var statusState = document.getElementById("status-state");
var statusConnection = document.getElementById("status-connection");

var statusDrink = document.getElementById("status-drink");
var statusOutlet = document.getElementById("status-outlet");

var statusButton = document.getElementById("status-button");
statusButton.onclick = statusClick;

var statusTimer = null;
var statusTime = 0;

var queuedDrink = {
    name: "",
    ingredients: {},
    outlet: ""
};

////////////////////////////////////////////////////////////////

pageView.onscroll = pageScrolled;

function pageScrolled() {
    let scroll = pageView.scrollLeft;
    let x = pageView.scrollLeft / windowWidth * 100;
    tabBar.style.transform = "translateX(" + x + "%)";

    if (scroll < windowWidth * 0.5) {
        if (currentPage != 0) {
            currentPage = 0;
            drinksTab.classList.add("selected");
            ingredientsTab.classList.remove("selected");
            userTab.classList.remove("selected");
        }
    } else if (scroll < windowWidth * 1.5) {
        if (currentPage != 1) {
            currentPage = 1;
            drinksTab.classList.remove("selected");
            ingredientsTab.classList.add("selected");
            userTab.classList.remove("selected");
        }
    } else {
        if (currentPage != 2) {
            currentPage = 2;
            drinksTab.classList.remove("selected");
            ingredientsTab.classList.remove("selected");
            userTab.classList.add("selected");
        }
    }
};

var currentPage = 0;

////////////////////////////////////////////////////////////////

var socket = null;
var socketConnected = false;
var socketAttempts = 0;

var uuid = localStorage.getItem('uuid');
if (uuid == null) {

    let array = new Uint8Array(16);
    self.crypto.getRandomValues(array);
    var uuid = "";
    for (let i = 0; i < 16; i++) {
        if (i == 4 || i == 6 || i == 8 || i == 10) {
            uuid += "-";
        }
        uuid += array[i].toString(16);
    };

    localStorage.setItem('uuid', uuid)
    console.log("new user: " + uuid);
}

const windowWidth = window.innerWidth;
const windowHeight = window.innerHeight;

const smallVH = windowHeight * 0.01;
const bigVH = document.getElementById('ruler').clientHeight * 0.02;

document.documentElement.style.setProperty('--vh', (windowHeight * 0.01) + "px");

socketInit();

console.log(3.5 % 2.0);

///////////////////////////////////////////////////////////////////////

const drawParticlesVS = `#version 300 es
    in vec2 position;
    in vec2 velocity;
    in vec4 color;

    uniform float ratio;
    uniform float pointSize;
    uniform vec2 dimensions;
    uniform float time;
    uniform vec2 bounds;

    out vec2 v_center;
    out vec4 v_color;

    void main() {
        vec2 farPosition = position + velocity*time + bounds*0.5;
        // float num = mod(mod(farPosition.x / bounds.x, 2.0) + 2.0, 2.0);
        // if(num > 1.0){
        //     farPosition.x = -farPosition.x;
        // }
        // num = mod(mod(farPosition.y / bounds.y, 2.0) + 2.0, 2.0);
        // if(num > 1.0){
        //     farPosition.y = -farPosition.y;
        // }

        vec2 modPosition = mod(mod(farPosition, bounds) + bounds, bounds) - bounds*0.5;

        gl_Position = vec4(modPosition.x, modPosition.y*ratio, 1, 1);
        gl_PointSize = pointSize;
        
        v_center = vec2((gl_Position.x + 1.0)*dimensions.x, (gl_Position.y + 1.0)*dimensions.y);
        v_color = color;
    }
    `;

const drawParticlesFS = `#version 300 es
    precision highp float;
    out vec4 outColor;

    uniform float deviation2;

    in vec2 v_center;
    in vec4 v_color;

    void main() {
        float amplitude = 0.4;
        vec2 diff = gl_FragCoord.xy - v_center;
        float length2 = (diff.x*diff.x) + (diff.y*diff.y);
        float intensity = amplitude * pow(2.71828, -0.5*(length2 / deviation2));

        outColor = vec4(v_color.rgb, intensity);
        //outColor = vec4(v_color.rgb, 0.4);
    }
    `;

// Get A WebGL context
/** @type {HTMLCanvasElement} */
const canvas = document.querySelector("#canvas");
const gl = canvas.getContext("webgl2");

gl.canvas.width = windowWidth;
gl.canvas.height = windowHeight;

const ratioWH = gl.canvas.width / gl.canvas.height;
const ratioHW = 1 / ratioWH;

const flareProgram = gl.createProgram();

const vshader = gl.createShader(gl.VERTEX_SHADER);
const fshader = gl.createShader(gl.FRAGMENT_SHADER);
gl.shaderSource(vshader, drawParticlesVS);
gl.shaderSource(fshader, drawParticlesFS);
gl.compileShader(vshader);
gl.compileShader(fshader);
gl.attachShader(flareProgram, vshader);
gl.attachShader(flareProgram, fshader);
gl.linkProgram(flareProgram);

const positionLoc = gl.getAttribLocation(flareProgram, 'position');
const velocityLoc = gl.getAttribLocation(flareProgram, 'velocity');
const colorLoc = gl.getAttribLocation(flareProgram, 'color');

const ratioLoc = gl.getUniformLocation(flareProgram, 'ratio');
const timeLoc = gl.getUniformLocation(flareProgram, 'time');
const boundsLoc = gl.getUniformLocation(flareProgram, 'bounds');
const deviationLoc = gl.getUniformLocation(flareProgram, 'deviation2');
const pointLoc = gl.getUniformLocation(flareProgram, 'pointSize');
const dimensionsLoc = gl.getUniformLocation(flareProgram, 'dimensions');

const flareVertexArray = gl.createVertexArray();
gl.bindVertexArray(flareVertexArray);

const vbo = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, vbo);

for (let i = 0; i < flareCount; i++) {
    let x = (Math.random() * 2 - 1) * (1 + flareSize);
    let y = (Math.random() * 2 - 1) * (ratioHW + flareSize);
    dv.setFloat32(28 * i, x, true);
    dv.setFloat32(28 * i + 4, y, true);

    let num = Math.random() * Math.PI * 2;
    dv.setFloat32(28 * i + 8, Math.cos(num) * flareSpeed, true);
    dv.setFloat32(28 * i + 12, Math.sin(num) * flareSpeed, true);
}

setTheme(theme, false);

gl.vertexAttribPointer(positionLoc, 2, gl.FLOAT, false, 28, 0);
gl.enableVertexAttribArray(positionLoc);

gl.vertexAttribPointer(velocityLoc, 2, gl.FLOAT, false, 28, 8);
gl.enableVertexAttribArray(velocityLoc);

gl.vertexAttribPointer(colorLoc, 3, gl.FLOAT, false, 28, 16);
gl.enableVertexAttribArray(colorLoc);



gl.enable(gl.BLEND);
gl.blendFunc(gl.SRC_ALPHA_SATURATE, gl.ONE);

gl.useProgram(flareProgram);
gl.viewport(0, 0, gl.canvas.width, gl.canvas.height);

gl.uniform2f(boundsLoc, 2 + 2 * flareSize, 2 * ratioHW + 2 * flareSize);
gl.uniform1f(ratioLoc, ratioWH);
gl.uniform1f(pointLoc, flareSize * gl.canvas.width);
gl.uniform1f(deviationLoc, Math.pow(flareSize * gl.canvas.width * 0.185, 2));
gl.uniform2f(dimensionsLoc, gl.canvas.width * 0.5, gl.canvas.height * 0.5);



function render(time) {

    gl.clear(gl.COLOR_BUFFER_BIT);

    gl.uniform1f(timeLoc, time * 0.001);
    gl.drawArrays(gl.POINTS, 0, flareCount);

    requestAnimationFrame(render);
}
requestAnimationFrame(render);