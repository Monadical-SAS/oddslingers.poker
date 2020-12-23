import React from 'react'
import ReactDOM from 'react-dom'
import {reduxify} from '@/util/reduxify'

import {createStore, combineReducers} from 'redux'
import {Provider} from 'react-redux'

import classNames from 'classnames'

import {websocket} from '@/websocket/reducers'
import {sidebet} from '@/sidebets/reducers'

import {SocketRouter} from '@/websocket/main'

import {Icon} from '@/components/icons'
import {tooltip} from '@/util/dom'

import Button from 'react-bootstrap/lib/Button'
import Row from 'react-bootstrap/lib/Row'
import Col from 'react-bootstrap/lib/Col'


const style = `
    h1.oddslingers-text-logo {
        text-align: left;
        font-size: 66px;
    }
    h2 {
        font-weight: 200;
        color: #333;
    }
    hr {
        margin-top: 12px;
        margin-bottom: 10px;
    }
    .tables-alert {
        margin: auto;
        width: 450px;
        text-align: center;
    }
    .tables-actions {
        float: right;
        margin-top: -50px;
    }
    .table-grid {
        text-align: center;
    }
    .table-grid .table-thumbnail {
        border: 3px solid #5cb85b;
        display: inline-block;
        text-align: center;
        float: none;
        vertical-align: top;
        margin-bottom: 10px;
        margin-right: 10px;
        margin-left: 10px;
    }
    @media (max-width: 665px) {
        .table-thumbnail {
            width: 94%;
        }
    }
    @media (max-width: 336px) {
        h1.oddslingers-text-logo {
            margin-top: -20px;
        }
        .table-thumbnail {
            width: 94%;
        }
    }
`

const BetTitles = () => {
    return <Row className={classNames("bet-row", "bets-titles")}>
        <Col md={2}
             className={classNames('table-path')}>
            <h4><b>Table Name</b></h4>
        </Col>
        <Col md={1}
             className={classNames('player-info')}>
            <h4><b>Player Username</b></h4>
        </Col>
        <Col md={2}
             className={classNames('st-stack-info')}>
            <h4><b>Initial Stack</b></h4>
        </Col>
        <Col md={1}
             className={classNames('cr-stack-info')}>
            <h4><b>Stack</b></h4>
        </Col>
        <Col md={1}
             className={classNames('odds-info')}>
            <h4><b>Odds</b></h4>
        </Col>
        <Col md={1}
             className={classNames('amt-info')}>
            <h4><b>Amount</b></h4>
        </Col>
        <Col md={1}
             className={classNames('bet-info')}>
            <h4><b>Current Amount</b></h4>
        </Col>
        <Col md={1}
             className={classNames('status-info')}>
            <h4><b>Status</b></h4>
        </Col>
        <Col md={2}
             className={classNames('status-info')}>
            <h4><b>Created</b></h4>
        </Col>
    </Row>
}

export class BetThumbnail extends React.PureComponent {
    constructor(props) {
        super(props)
    }
    componentDidMount() {
        if (!this.props.collapse) {
            const bet_id = this.props.bet.id
            const main_bet_id = this.props.bet.sidebet_parent_id
            $(`#${bet_id}`).on('show.bs.collapse', function () {
                $(`#${main_bet_id}-icon`).addClass('active');
            });

            $(`#${bet_id}`).on('hide.bs.collapse', function () {
                $(`#${main_bet_id}-icon`).removeClass('active');
            });
        }
    }
    render() {
        const {collapse, classname, bet} = this.props
        return <Row className={classNames("bet-row", classname)} id={`${bet.id}`}>
            <a href={bet.table.path}>
                <Col md={2}
                     className={classNames('table-path')}>
                    <h4><b>{bet.table.name}</b> <Icon name='external-link'/></h4>
                </Col>
            </a>
            <Col md={1}
                 className={classNames('player-info')}>
                <h4><b>{bet.player.username}</b></h4>
            </Col>
            <Col md={2}
                 className={classNames('st-stack-info')}>
                <h4><b>{bet.starting_stack}</b></h4>
            </Col>
            <Col md={1}
                 className={classNames('cr-stack-info')}>
                <h4><b>{bet.current_stack}</b></h4>
            </Col>
            <Col md={1}
                 className={classNames('odds-info')}>
                <h4><b>{bet.odds}</b></h4>
            </Col>
            <Col md={1}
                 className={classNames('amt-info')}>
                <h4><b>{bet.amt}</b></h4>
            </Col>
            <Col md={1}
                 className={classNames('bet-info', bet.value_class)}>
                <h4><b>{bet.current_value}</b></h4>
            </Col>
            <Col md={1}
                 className={classNames('status-info')}>
                <h4><b>{bet.status}</b></h4>
            </Col>
            <Col md={2}
                 className={classNames('created-info')}>
                <h4><b>{bet.created}</b></h4>
            </Col>
            {collapse &&
                <Col xs={12}>
                    <span data-toggle="collapse" data-target={`.${bet.id}`}
                          aria-expanded="false" aria-controls={`${bet.id}`}>
                            <Icon name='angle-down fa-3x'
                                  id={`${bet.id}-icon`}
                                  {...tooltip('Show carried bets', 'top')}/>
                    </span>
                </Col>}
        </Row>
    }
}


export const BetThumbnails = reduxify({
    mapStateToProps: (state) => {
        const bets = state.sidebet.bets || []
        const initial_bets = bets.filter(bet => bet.sidebet_parent_id === null)
        const grouped_bets = initial_bets.map(bet => {
            const children = bets.filter(child => child.sidebet_parent_id === bet.id)
            return {
                main: bet,
                children
            }
        })
        return {grouped_bets}
    },
    render: ({grouped_bets}) => {
        return grouped_bets.map((bet, i) => <div>
                <BetThumbnail collapse={bet.children.length > 0} bet={bet.main} key={`${bet.main.id}-${i}`}/>
                {bet.children.map((child, j) =>
                    <BetThumbnail collapse={false}
                                  bet={child}
                                  classname={`collapse ${bet.main.id}`}
                                  key={`${child.id}-${j}`}/>)}
            </div>)
    }
})


export const PopularTable = ({table}) => {

    return <Row className="popular-tables-row">

        <a href={table.path}>
            <Col md={3}
                 className={classNames('table-info')}>
                <h4><b>{table.name}</b></h4>
            </Col>
        </a>
            <Col md={3}
                 className={classNames('player-info')}>
                <h4><b>{table.player.username}</b></h4>
            </Col>
            <Col md={2}
                 className={classNames('pls-info')}>
                <h4><b>{table.odds}</b></h4>
            </Col>
            <Col md={2}
                 className={classNames('gainings-info')}>
                <h4><b>{table.amt}</b></h4>
            </Col>
            <Col md={2}
                 className={classNames('gainings-info')}>
                <Button bs="success">Bet</Button>
            </Col>
    </Row>
}

export const TotalRowComponent = ({total, classname, text}) => {
    return <Row className="total-row">
            <Col md={1} mdOffset={7}>
                <h4><b>Total</b></h4>
            </Col>
            <Col md={1} className={classNames(classname)}>
                <h4><b>{total}</b></h4>
            </Col>
            <Col md={1}>
                <h4><b>{text}</b></h4>
            </Col>
        </Row>
}

export const TotalRow = reduxify({
    mapStateToProps: (state) => {
        const initial_total = state.sidebet.total || 0
        const total = Math.abs(initial_total)
        if (initial_total > 0) {
            return {total, classname: 'green', text: 'Won'}
        }
        return {total, classname: 'red', text: 'Lost'}
    },
    render: (props) => {
        return <TotalRowComponent key="total-rows" {...props} />
    }
})

export const PopularTables = reduxify({
    mapStateToProps: (state) => {
        const tables = state.sidebet.tables || []
        return {tables}
    },
    render: ({tables}) => {
        return tables.map((table, i) =>
            <PopularTable table={table} key={`${table.name}-${i}`}/>)
    }
})

class ReloadButton extends React.PureComponent {
    constructor(props) {
        super(props)
        this.state = {disabled: false}
    }
    onClick() {
        if (!this.state.disabled) {
            global.page.socket.send_action('UPDATE_SIDEBET')
            this.setState({...this.state, disabled: true})
            setTimeout(() => {
                this.setState({...this.state, disabled: false})
            }, 4000)
        }
    }
    render() {
        return <Button onClick={::this.onClick}>
            Reload <Icon name='refresh'/>
        </Button>
    }
}


class BetList extends React.Component {
    constructor(props) {
        super(props)
    }
    render() {
        return <div className="table-grid">
            <style>{style}</style>

            <Row>
                <h1 className="oddslingers-text-logo">
                    Sidebets <ReloadButton/>
                </h1>
                <hr/>
            </Row>
            <br/>
            <BetTitles/>
            <BetThumbnails/>
            <hr/>
            <TotalRow/>
            <hr/>

            <br/>
            <br/>
            <h1 className="oddslingers-text-logo text-center">
                Popular Tables
            </h1>
            <hr/>
            <br/>
            <PopularTables/>
        </div>
    }
}


export const Sidebet = {
    view: 'ui.views.pages.Sidebet',

    init(props) {
        const time = {
            getActualTime: () => Date.now(),
            setActualTime: () => {}
        }
        const store = this.setupStore({websocket, sidebet}, {})
        const socket = this.setupSocket(store, time)
        this.setupState(store, props)
        const interval = this.setupInterval(socket)

        window.onbeforeunload = ::this.tearDown
        return {socket, store, interval}
    },
    setupInterval(socket) {
        return setInterval(() => {
            this.onSendAction(socket)
        }, 8000)
    },
    onSendAction(socket) {
        socket.send_action('UPDATE_SIDEBET')
    },
    setupStore(reducers, initial_state) {
        // create the redux store for the page
        return createStore(combineReducers(
            reducers,
            initial_state,
        ))
    },
    setupSocket(store, time) {
        // create the websocket connection to the backend
        if (!global.WebSocket) return {name: 'MockSocket', close: () => {}}

        return new SocketRouter(
            store,
            global.navbarMessage,
            global.loadStart,
            global.loadFinish,
            '',
            time
        )

    },
    setupState(store, props) {
        store.dispatch({
            type: 'UPDATE_SIDEBET',
            bets: props.bets,
            tables: props.tables,
            total: props.total
        })
    },
    tearDown() {
        if(global.page.socket) global.page.socket.close()
        if(global.page.interval) clearInterval(global.page.interval)
    },
    render({store}) {
        return <Provider store={store}>
            <BetList/>
        </Provider>
    },
    mount(props, mount_point) {
        global.page = this.init(props)
        ReactDOM.render(
            this.render(global.page),
            mount_point,
        )
    }
}


if (global.react_mount) {
    // we're in a browser, so mount the page
    Sidebet.mount(global.props, global.react_mount)
}
