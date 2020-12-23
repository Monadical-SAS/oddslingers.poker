import React from 'react'


const directions = {
    37: {x: -1, y: 0 }, // Left
    38: {x: 0 , y: -1}, // Up
    39: {x: 1 , y: 0 }, // Right
    40: {x: 0 , y: 1 }, // Down
}

const multiply_to_nearest = (amt1, amt2, nearest=100) => {
    const res = amt1 * amt2
    return res - mod(res, nearest)
}

const collides = (square1, square2) =>
    square1.x == square2.x && square1.y == square2.y;

const collides_with_snake = (snake, square) =>
    snake.reduce((out, segment) => out || collides(segment, square), false)

// weird math becuase JS modulo
// stackoverflow.com/questions/4467539/javascript-modulo-not-behaving
const mod = (m, n) =>
    ((m % n) + n) % n

class SnakeGame {
    constructor(elem){
        this.elem = elem
        this.ctx = elem.getContext('2d')
        this.new_game()
    }
    new_game() {
        this.dims = [this.elem.width/20, this.elem.height/20];
        this.gamesize = {x: this.elem.width, y: this.elem.height}
        this.snake = [{x: 5, y:5}];
        this.new_apple();
        this.direction = null;
        this.next_direction = null;
        this.input_queue = [];
    }
    collides_with(snake, square) {
        return snake.reduce(
            (dead, segment) => collides(segment, square), 
        false)
    }
    new_apple() {
        if (this.snake.length >= this.dims[0] * this.dims[1]) this.new_game();
        do {
            this.apple = {
                x: Math.floor(Math.random() * this.dims[0]),
                y: Math.floor(Math.random() * this.dims[1]),
            }
        } while (collides_with_snake(this.snake, this.apple));
    }
    is_dead(new_segment) {
        return collides_with_snake(this.snake.slice(1), new_segment);
    }
    step() {
        this.direction = this.get_next_direction();
        if (!this.direction) return;
        const head = this.snake[this.snake.length - 1];
        let [dx, dy] = this.dims;
        const new_segment = {
            x: mod(head.x + this.direction.x, dx),
            y: mod(head.y + this.direction.y, dy),
        };
        
        if (this.is_dead(new_segment)) this.new_game();

        if (collides(new_segment, this.apple)){
            this.new_apple();
        } else if (this.snake.length > 5) {
            this.snake.shift();
        }
        this.snake.push(new_segment);
        this.draw()
    }
    draw() {
        this.ctx.clearRect(0, 0, this.gamesize.x, this.gamesize.y);
        this.ctx.fillStyle = "black";
        this.ctx.strokeStyle = "black 2px solid";
        let dimx, dimy, sx, sy;
        [dimx, dimy] = this.dims;
        sx = (this.gamesize.x / dimx);
        sy = (this.gamesize.y / dimy);

        for (let segment of this.snake) {
            let {x, y} = segment;
            this.ctx.fillRect(sx * x, sy * y, sx - 1, sy - 1);
        }
        this.ctx.fillStyle = "red";
        let {x, y} = this.apple;
        this.ctx.fillRect(sx * x, sy * y, sx, sy);
    }
    get_next_direction() {
        if (!this.next_direction) return this.direction;
        if (!this.direction) return this.next_direction;
        let {x, y} = this.next_direction;
        if ( (x == this.direction.x || y == this.direction.y))
            return this.direction; // cannot eat self
        return this.next_direction;
    }
    keypress(event) {
        if (directions[event.keyCode]) {
            event.preventDefault();
            event.stopPropagation();
        }
        this.next_direction = directions[event.keyCode] || this.next_direction;
    }
}


export class Snake extends React.Component {
    constructor(props) {
        super(props)
        this.state = {started: false}
    }
    onCanvasMount(elem) {
        if (!elem) debugger
        this.dom = elem
        this.game = new SnakeGame(this.dom)
        window.onkeydown = this.game.keypress.bind(this.game)
        if (this.interval)
            clearInterval(this.interval)
        this.interval = setInterval(() => {
            this.game.step()
            this.game.draw()
        }, 100)
    }
    componentDidMount() {
        window.onkeydown = ::this.onKeyDown
    }
    componentWillUnmount() {
        clearInterval(this.interval)
        window.onkeydown = undefined
        this.game = null
    }
    onKeyDown(event) {
        if (!this.dom) return
        if (directions[event.keyCode] && !this.state.started) {
            this.setState({started: true})
        }
    }
    render() {
        const style = {
            backgroundcolor: 'rgba(0,0,0,0.2)',
            ...(this.props.style || {})
        }
        return this.state.started ?
            <canvas
                id="snake"
                style={{style}}
                width={multiply_to_nearest(global.innerWidth, 0.35, 20)}
                height={multiply_to_nearest(global.innerWidth, 0.15, 20)}
                ref={(elem) => {this.onCanvasMount(elem)}}>
            </canvas>
          : <div className="show-on-hover" style={{
                width: '100%',
                height: multiply_to_nearest(global.innerWidth, 0.15, 20),
                fontSize: '0.6vw',
                textAlign: 'center'}}>

                Press the arrow keys to kill some time.
            </div>
    }
}

