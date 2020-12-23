import React from 'react'
import ReactDOM from 'react-dom'
import classNames from 'classnames'

import distanceInWordsToNow from 'date-fns/distance_in_words_to_now'

import Button from 'react-bootstrap/lib/Button'
import Row from 'react-bootstrap/lib/Row'
import Col from 'react-bootstrap/lib/Col'
import Alert from 'react-bootstrap/lib/Alert'
import Checkbox from 'react-bootstrap/lib/Checkbox'
import Tabs from 'react-bootstrap/lib/Tabs'
import Tab from 'react-bootstrap/lib/Tab'

import {Icon} from '@/components/icons'
import {SearchField} from '@/components/search-field'

import {DealerIcon} from '@/poker/components/board'
import {tooltip} from '@/util/dom'
import {CSRFToken} from '@/util/react'
import {range, chipAmtStr} from '@/util/javascript'
import {getSearchHashInUrl, asyncGetUserBalance} from '@/util/browser'
import {THRESHOLD_BB_FOR_BOTS} from '@/constants'


const style = `
    h1{
        color: #1171d6;
    }
    h2 {
        font-weight: 200;
        color: #333;
    }
    h4 .grey {
        opacity: 0.7;
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
    .table-grid {
        text-align: center;
    }
    .table-args {
        margin-top: 10px;
        height: auto;
    }
    .table-args span.one-column-field {
        display: inline-block;
        vertical-align: top;
        margin-right: 10px;
        width: 30%;
    }
    .tables-filters .checkbox {
        display: inline-block;
    }
    .table-grid .table-thumbnail {
        border-radius: 10px;
        display: inline-block;
        text-align: center;
        float: none;
        vertical-align: top;
        margin-bottom: 20px;
        margin-right: 12px;
        margin-left: 12px;
        height: 370px;
        padding: 20px;
        background-color: white;
        box-shadow: 0px 3px 16px 5px rgba(0,0,0,0.02);
        transition: 300ms box-shadow;
        position: relative;
    }
    .table-grid .table-thumbnail .tooltip {
        opacity: 1;
    }
    .table-grid .table-thumbnail .ui-tooltip-content {
    }
    .table-grid .table-thumbnail:hover {
        box-shadow: 0px 7px 16px 6px rgba(0, 0, 0, 0.10);
        transition: 200ms box-shadow;
    }
    .table-grid .table-thumbnail .new-table {
        text-align: center;
        border-radius: 4px;
    }
    .new-table {
        color: black;
    }
    .new-table .row-options input {
        width: 47%;
    }
    .players-list {
        color: #3a3a3b;
        margin: 0px;
        padding: 0px;
        border-radius: 5px;
        height: 200px;
        box-shadow: 0px 6px 8px 2px rgba(92, 184, 91, 0.03);
        z-index: 200;
        border: 2px solid rgba(92, 184, 91, 0.54);
    }
    .tournament .players-list {
        box-shadow: 0px 6px 8px 2px rgba(81, 58, 183, 0.03);
    }
    .new-table input {
        margin-right: 5px;
    }
    .new-table input, .new-table select {
        margin-bottom: 5px;
    }
    .new-table .one-column-field input {
        width: 100%;
    }
    #new-table-name, #new-tourney-name {
        width: 90%;
        margin-bottom: 5px;
    }
    .player-count {
        text-align: center;
        font-size: 20px;
        right: -215px;
        margin-bottom: 2px;
        padding: 10px 0px;
        z-index: 200;
        margin-bottom: 10px;
        background: rgba(92, 184, 91, 0.54);
        color: #fafafa;
        text-shadow: 0px 1px 5px rgba(0, 0, 0, 0.45);
    }
    .table-thumbnail .btn-success {
        margin-top: 0px;
        height: 60px;
        opacity: 1;
        float: none;
        width: 80%;
        display: inline-block;
        font-size: 1.15em;
        box-shadow: 0px 3px 16px 5px rgba(0,0,0,0.1);
    }
    .table-thumbnail .player-row {
        margin-left: 10px;
        margin-right: 10px;
        font-size: 14px;
        text-align: center;
    }

    .new-table-btn {
        margin-left: 11px;
    }
    .table-preview {
        margin-left: -10px;
        margin-right: -10px;
        margin-bottom: 10px;
    }
    .table-preview img {
        width: 100%;
    }
    #ml-ref {
        margin-left: 15px;
        vertical-align: bottom;
    }
    #new-table-link {
        margin-left: 10px;
    }
    .clbl {
        color: #333;
    }
    .table-thumbnail ul.nav-pills {
        width: 210px;
        margin: auto;
    }
    li.active #type-of-game-tab-1 {
        background-color: #5cb85b;
        color: rgb(255, 255, 255);
    }
    li.active #type-of-game-tab-2 {
        color: rgb(255, 255, 255);
        background-color: rgba(81, 58, 183, 0.9);
        margin-left: 3px;
    }
    #type-of-game-pane-2 .btn-success {
        background-color: rgba(81, 58, 183, 0.9);
    }

    #search-field {
        border-top-left-radius: 4px;
        border-bottom-left-radius: 4px;
        height: 35px;
    }

    .vertical-aligned {
        margin-top: 7px;
    }

    .vertical-aligned #new-tourney-buyin {
        vertical-align: top;
    }

    .hideable-table-name, .hideable-tournament-name {
        display: none;
    }

    #no-bots-info {
        display: none;
    }
    .label-filter {
        font-weight: normal;
        margin-left: 5px;
        cursor: pointer;
        vertical-align: top;
    }

    @media (max-width: 850px) {
        h1 small {
            display: none;
        }
    }

    @media (max-width: 767px) {
        h1.oddslingers-text-logo  {
            text-align: center;
            font-size: 66px;
            margin-top: -15px;
        }
        h1 small {
            font-size: 0.4em;
            display: block;
        }
        .tables-alert {
            margin-top: 4px;
            margin-bottom: 8px;
            width: 100%;
        }
        #react > .table-grid {
            padding: 20px;
        }
        .table-thumbnail {
            float: none;
            margin: auto;
        }
        .new-table-btn {
            margin-top: 11px;
        }
    }
    @media (max-width: 768px) {
        .table-thumbnail {
            width: 94%;
        }
        .new-table .row-options input {
            width: 44%;
        }
    }
    @media (max-width: 336px) {
        h1.oddslingers-text-logo {
            margin-top: -20px;
        }
        .table-thumbnail {
            width: 94%;
        }
        #new-table-link {
            margin-top: 10px;
            margin-left: 0;
        }
    }
    @media (max-width: 425px) {
        .tables-actions, .tables-filters {
            text-align: center;
        }
    }
`

const isMe = (username) => username
                           && global.user
                           && username == global.user.username

const activity_colors = [
    'gray',
    'orange',
    'orange',
    'orange',
    'orange',
    'green',
]

const PRIVATE_TOOLTIP_TEXT = `
Private games don't get listed on the games page. Use it to play with friends!
`

const locked_tooltip_text = (no_level=true) => `
<div style="width:180px">Only available as a spectator.</br>
${no_level ? 'Earn more chips to unlock!' : 'Verify your email address to play'}</div>
`

export const TableThumbnail = ({table}) => {

    const is_user_table = !(global.user === null)
                          && Object.values(table.players)
                                   .map((d) => d.username)
                                   .indexOf(global.user.username) !== -1

    const has_free_seats = Object.keys(table.players).length < table.num_seats

    const round_str = (decimal) =>
        Math.round(Number(decimal)).toLocaleString()

    return (
        <a className="overlay" href={table.path}>
        <Col sm={2}
             className={classNames('table-thumbnail', {'my-table': is_user_table})}>
            <h4 style={{fontSize: '1.45em'}}>
                <span className="grey">
                    {table.featured &&
                        <Icon name="star"
                              style={{marginRight: 8, color: '#1171d6'}}
                              title="Featured Game"/>}
                    {table.name}
                </span>
                {(global.user && table.is_locked) &&
                    <Icon name="lock" data-html="true"
                          style={{position: 'absolute', right: 15, color: 'gray', fontSize: 24}}
                          {...tooltip(locked_tooltip_text(global.user.cashtables_level < table.bb))}/>}
            </h4>
            {table.hotness_level ?
                    <Icon name="circle-o"
                          style={{color: activity_colors[table.hotness_level]}}
                          title={`Last activity: ${distanceInWordsToNow(table.modified)} ago`}/>
                  : <Icon name="circle-o"
                          style={{color: '#ddd'}}
                          title="Waiting for more players..."/>}
                &nbsp;&nbsp;
            {table.displayable_variant}
            &nbsp;&nbsp;
            <a href={`/learn#${table.variant}`} target="_blank">
                <Icon name="question-circle-o" data-html="true"
                      {...tooltip("<div style='min-width:150px'>Game type variant.<br/>Click for more info</div>")}/>
            </a>
            <br/><br/>
            <div style={{textAlign: 'center', fontWeight: 400, opacity: 0.8}}>
                Blinds: {chipAmtStr(table.sb)}/{chipAmtStr(table.bb)}
                &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;
                Min Buyin: {chipAmtStr(table.min_buyin)}
                &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;
                {table.stats &&
                    <span style={{color: 'blue'}}
                          data-html="true"
                          {...tooltip(`Players per Flop Ratio: ${round_str(table.stats.players_per_flop_pct)}</br>
                                       Average Pot: ${round_str(table.stats.avg_pot)}</br>
                                       Hands per Hour: ${round_str(table.stats.hands_per_hour)}`)}>
                        Stats
                    </span>}
            </div>
            <br/>
            <div className="players-list" style={{borderColor: (has_free_seats && table.hotness_level) ? '#5cb85b' : 'rgba(92, 184, 91, 0.84)'}}>
                <div className="player-count" style={{background: (has_free_seats && table.hotness_level) ? '#5cb85b' : 'rgba(92, 184, 91, 0.84)'}}>
                    <Icon name="users" title="Seats Available" style={{opacity: 0.6}}/>
                    &nbsp;&nbsp;
                    {Object.keys(table.players).length}/{table.num_seats}
                </div>
                {range(table.num_seats).map(position =>
                    table.players[position] === undefined ?
                        <Row className="player-row" key={position}>
                            <Col xs={2} style={{textAlign: "center", opacity: 0.2}}>
                                {(table.btn_idx === position) ?
                                    <DealerIcon style={{marginLeft: -3}}/>
                                   : (position + 1)}
                            </Col>
                            <Col xs={6} style={{color: "rgb(123, 123, 123)", textAlign: "left"}}>(empty)</Col>
                            <Col xs={4}></Col>
                        </Row>
                    :
                        <Row className="player-row" key={position}>
                            <Col xs={2} style={{textAlign: "center", opacity: 0.7}}>
                                {(table.btn_idx === position) ?
                                    <DealerIcon style={{marginLeft: -3}}/>
                                   : (position + 1)}
                            </Col>
                            <Col xs={6} style={{
                                textAlign: "left",
                                fontWeight: isMe(table.players[position].username)?
                                            800 : "initial",
                            }}>
                                {table.players[position].username}
                            </Col>
                            <Col xs={4} style={{
                                textAlign: "right",
                                fontWeight: isMe(table.players[position].username)?
                                            800 : "initial",
                            }}>
                                <b title={table.players[position].stack}>
                                    {chipAmtStr(table.players[position].stack, true)}
                                </b>
                            </Col>
                        </Row>
                )}
            </div>
            {(global.user && global.user.is_superuser) ?
                <form action="/api/table/archive/" method="POST" target="_blank">
                    <CSRFToken/>
                    <input type="hidden" name="id" value={table.id}/>
                    <Button type="submit" bsStyle="info">Archive</Button>
                </form> : null}
        </Col>
        </a>
    )
}

export const TournamentThumbnail = ({ tournament }) => {

    const is_user_tournament = !(global.user === null)
        && Object.values(tournament.entrants)
            .map((d) => d.username)
            .indexOf(global.user.username) !== -1

    const has_free_seats = Object.keys(tournament.entrants).length < tournament.max_entrants

    return (
        <Col sm={2}
             className={classNames('table-thumbnail', 'tournament', {
                'my-table': is_user_tournament,
             })}>
            <a className="overlay" href={tournament.path}></a>
            <h4 style={{fontSize: '1.45em'}}>
                <span className="grey">
                    {tournament.name}
                </span>
                {(global.user && tournament.is_locked) &&
                    <Icon name="lock" data-html="true"
                          style={{position: 'absolute', right: 15, color: 'gray', fontSize: 24}}
                          {...tooltip(locked_tooltip_text())}/>}
            </h4>
            <Icon name="diamond" style={{color: 'red'}} title="Join a tournament for 5k free chips!"/>
            &nbsp;&nbsp;
            {tournament.displayable_variant}
            &nbsp;&nbsp;
            <a href={`/learn#${tournament.variant}`} target="_blank">
                <Icon name="question-circle-o" data-html="true"
                      {...tooltip("<div style='min-width:150px'>Game type variant.<br/>Click for more info</div>")}/>
            </a>
            <br/>
            <br/>
            <div style={{textAlign: 'center', fontWeight: 400, opacity: 0.8}}>
                Buyin: {chipAmtStr(tournament.buyin_amt)}
                &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;
                <span onClick={() => window.open(tournament.path)} style={{color: 'blue'}}>Tournament</span>
            </div>
            <br/>
            <div className="players-list" style={{borderColor: has_free_seats ? 'rgba(81, 58, 183, 0.9)' : 'rgba(81, 58, 183, 0.1)'}}>
                <div className="player-count" style={{background: has_free_seats ? 'rgba(81, 58, 183, 0.9)' : 'rgba(81, 58, 183, 0.1)'}}>
                    <Icon name="users" title="Players" style={{opacity: 0.6}}/>
                    &nbsp;&nbsp;
                    {Object.keys(tournament.entrants).length}/{tournament.max_entrants}
                </div>
                {range(tournament.max_entrants).map(position =>
                    tournament.entrants[position] === undefined ?
                        <Row className="player-row" key={position}>
                            <Col xs={2} style={{textAlign: "left"}}>
                            </Col>
                            <Col xs={6} style={{color: "rgb(123, 123, 123)", textAlign: "left"}}>
                                (empty)
                            </Col>
                        </Row>
                        :
                        <Row className="player-row" key={position}>
                            <Col xs={2} style={{textAlign: "left"}}>
                            </Col>
                            <Col xs={6} style={{
                                textAlign: "left",
                                fontWeight: isMe(tournament.entrants[position].username) ?
                                    800 : "initial",
                            }}>
                                {tournament.entrants[position].username}
                            </Col>
                        </Row>
                )}
            </div>
        </Col>
    )
}

const blinds = (cashGameBBs, thresholdBBEmailVerified) => {
    if (!global.user) return cashGameBBs.slice(0, 1)
    if (global.user.has_verified_email)
        return cashGameBBs.filter(bb => bb <= global.user.cashtables_level)
    else
        return cashGameBBs.filter(bb =>
            bb <= global.user.cashtables_level
            && bb < thresholdBBEmailVerified
        )
}

const blinds_changed = (e) => {
    const no_bots = e.target.value > THRESHOLD_BB_FOR_BOTS
    $('#new-table-num-bots').prop("disabled", no_bots)
    $('#no-bots-info').toggle(no_bots)
    if (no_bots){
        $('#new-table-num-bots').val(0)
    }
}

const onPrivateClick = (target) =>
    $(`.hideable-${target}-name`).toggle()

const TableForm = ({onNewTable, cashGameBBs, thresholdBBEmailVerified, state}) =>
    <div>
        {global.user &&
            <div className="table-args">
                <Checkbox id="is-private-table"
                          onClick={() => onPrivateClick('table')}>
                    Private
                    &nbsp;<Icon name="info-circle"
                                {...tooltip(PRIVATE_TOOLTIP_TEXT, 'top')}/>
                </Checkbox>
                <span className="hideable-table-name">Name:</span>
                <input id="new-table-name"
                       className="hideable-table-name"
                       type="text"
                       placeholder={`${global.user.username}'s Table`}
                       onClick={() => false}/>
                <br className="hideable-table-name"/>
                <div id='new-table-row'>
                    <div id='new-table-column'>
                        Type:<br/>
                        <select id="new-table-tabletype">
                            <option value="NLHE">No Limit Hold'em</option>
                            <option value="BNTY">No Limit Bounty</option>
                            <option value="PLO">Pot Limit Omaha</option>
                        </select>
                    </div>
                    <div id='new-table-column'>
                        Blinds:<br/>
                        <select id="new-table-bettype"
                                onChange={blinds_changed}>
                            {blinds(cashGameBBs, thresholdBBEmailVerified).map(bb =>
                                <option key={bb} value={bb}>{`SB ${bb/2} / BB ${bb}`}</option>)}
                        </select>
                    </div>
                </div>
                <br/>
                <Row className="row-options">
                    <Col xs={6}>
                        Seats:&nbsp; <input id="new-table-num-seats"
                                            type="number"
                                            min={2}
                                            max={6}
                                            defaultValue={6}
                                            placeholder={6}
                                            onClick={() => false}/>
                    </Col>
                    <Col xs={6}>
                        Bots:&nbsp;
                        <input id="new-table-num-bots"
                                type="number"
                                min={0}
                                max={5}
                                defaultValue={0}
                                placeholder={0}
                                onClick={() => false}/>
                        <Icon name="info-circle" id="no-bots-info"
                            {...tooltip('Only humans can play these blinds', 'top')}/>
                    </Col>
                </Row>
                {state.errors.map(error =>
                    <div key={error} className='red-color'>{error}</div>)}
            </div>}

        <hr/>
        <Button className={classNames(global.user && 'center-create-btn')}
                onClick={() => onNewTable(false)}
                bsStyle="success">

            Create New Cash Table &nbsp;<Icon name="plus"/>
        </Button>
    </div>

const buyin_amts = (tourneyBuyinAmts) => {
    if (!global.user) return tourneyBuyinAmts
    return tourneyBuyinAmts.filter(buyin_amt =>
        buyin_amt <= global.user.tournaments_level
    )
}
const can_create_tournaments = (tourneyBuyinAmts) => {
    if (!global.user) return true
    return global.user.tournaments_level >= tourneyBuyinAmts[0]
}

const TournamentForm = ({onNewTable, tourneyBuyinAmts, state}) =>
    <div>
        {!can_create_tournaments(tourneyBuyinAmts) &&
            <div className='red-color'>
                <br/><br/><br/><br/><br/>
                    You cannot create tournaments yet
            </div>
        }
        {global.user && can_create_tournaments(tourneyBuyinAmts) &&
            <div className="table-args">
                <Checkbox id="is-private-tourney"
                          onClick={() => onPrivateClick('tournament')}>
                    Private
                    &nbsp;<Icon name="info-circle"
                                {...tooltip(PRIVATE_TOOLTIP_TEXT, 'top')}/>
                </Checkbox>
                <span className="hideable-tournament-name">Name:</span>
                <input id="new-tourney-name"
                       className="hideable-tournament-name"
                       type="text"
                       placeholder={`${global.user.username}'s Tournament`}
                       onClick={() => false}/>
                <br className="hideable-tournament-name"/>
                Type:<br/>
                <select id="new-tourney-tabletype">
                    <option value="NLHE">No Limit Hold'em</option>
                    <option value="BNTY">No Limit Bounty</option>
                    <option value="PLO">Pot Limit Omaha</option>
                </select>
                <br/>
                <br/>
                <Row className="row-options">
                    <Col xs={6}>
                        Buyin:
                        <select id="new-tourney-buyin">
                            {buyin_amts(tourneyBuyinAmts).map(amt =>
                                <option key={amt} value={amt}>{chipAmtStr(amt)}</option>)}
                        </select>
                    </Col>
                    <Col xs={6}>
                        Entrants:
                        <input id="new-tourney-num-seats"
                                type="number"
                                min={2}
                                max={6}
                                defaultValue={6}
                                placeholder={6}
                                onClick={() => false}/>
                    </Col>
                </Row>
                {state.errors.map(error =>
                    <div key={error} className='red-color'>{error}</div>)}
            </div>
        }
        <hr/>
        {can_create_tournaments(tourneyBuyinAmts) &&
            <Button className={classNames(global.user && 'center-create-btn')}
                    onClick={() => onNewTable(true)}
                    bsStyle="success">
                Create New Tourney &nbsp;<Icon name="plus"/>
            </Button>
        }
    </div>

/* const sortByDateAndBBs = (tables) =>
    tables.sort((a, b) => a.bb - b.bb)
          .sort((a, b) => a.modified - b.modified)

const tableHasMe = (table) => {
    if (!global.user) {
        return false
    }
    return Object.values(table.players || table.entrants)
                 .some(({ username }) => username === global.user.username)
} */

class TableList extends React.Component {
    constructor(props) {
        super(props)
        const now = Date.now()
        this.state = {
            search: getSearchHashInUrl(),
            now: now,
            updated: distanceInWordsToNow(now),
            show_cash_tables: true,
            show_tournaments: true,
            show_locked: true,
            show_plo: true,
            show_nlhe: true,
            show_bnty: true,
            errors: [],
            filter_errors: []
        }

        // get user balance async
        asyncGetUserBalance()
    }
    validate(args) {
        let errors = []

        if (!args.is_tournament && (args.num_bots >= args.num_seats)) {
            errors.push("Num seats should be greater than num bots")
        }

        if (args.is_tournament &&
                (Number(global.user.balance) < Number(args.min_buyin))) {
            errors.push("You don't have enough funds to play")
        }

        if (
            Number(args.num_bots) > 0
            && args.table_type === 'PLO'
            && Number(args.sb) > 1
        ) {
            errors.push("Can't add bots to PLO games with blinds bigger than 1/2")
        }

        return errors
    }
    onNewTable(is_tournament=false) {
        if (!global.user) {
            global.location = '/accounts/login/?next=/tables/#newtable'
            return
        }
        // post creates a new table
        const element = is_tournament ? 'tourney' : 'table'
        const args = {
            'table_type': $(`#new-${element}-tabletype`).val() || '',
            'table_name': $(`#new-${element}-name`).val() || '',
            'num_seats': $(`#new-${element}-num-seats`).val() || 0,
            'num_bots': $('#new-table-num-bots').val() || 0,
            'min_buyin': $(`#new-${element}-buyin`).val(),
            'is_tournament': is_tournament,
            'sb': ($('#new-table-bettype').val() || 2) / 2,
            'bb': $('#new-table-bettype').val() || 2,
            'is_private': $(`#is-private-${element}`).is(':checked')
        }
        const errors = this.validate(args)
        this.setState({errors}, () => this.postNewTable(args))
    }
    postNewTable(args) {
        if (!this.state.errors.length) {
            $.post('?', args, (response) => {
                if (response.path)
                    global.location = response.path
            })
        }
    }
    componentDidMount() {
        $("#new-table-link").on('click', () => {
            $("#new-table-container").addClass("active")
        })
        setInterval(() => {
            this.setState({'updated': distanceInWordsToNow(this.state.now)})
        }, 60000)
    }
    filterTables() {
        const featured_table = this.props.tables.find(
            table => table.featured
        )
        const unlocked_tables = this.props.tables.filter(
            table => !table.featured && !table.is_locked
        )
        const locked_tables = this.props.tables.filter(
            table => !table.featured && table.is_locked
        )
        const unlocked_tournaments = this.props.tournaments.filter(
            tournament => !tournament.is_locked
        )
        const locked_tournaments = this.props.tournaments.filter(
            tournament => tournament.is_locked
        )

        let tables = [
            featured_table,
            ...unlocked_tables,
            ...unlocked_tournaments,
            ...locked_tables,
            ...locked_tournaments,
        ]
        const {
            search, show_cash_tables, show_tournaments,
            show_plo, show_nlhe, show_bnty, show_locked,
        } = this.state

        if (search) {
            tables = tables.filter(
                table => table.name.toLowerCase().includes(search.toLowerCase())
            )
        }

        if (!show_cash_tables) {
            tables = tables.filter(table => table.is_tournament)
        }

        if (!show_tournaments) {
            tables = tables.filter(table => !table.is_tournament)
        }

        if (!show_plo) {
            tables = tables.filter(table => table.variant !== 'PLO')
        }

        if (!show_nlhe) {
            tables = tables.filter(table => table.variant !== 'NLHE')
        }

        if (!show_bnty) {
            tables = tables.filter(table => table.variant !== 'BNTY')
        }

        if (!show_locked) {
            tables = tables.filter(table => !table.is_locked)
        }

        return tables
    }
    onFilter(query) {
        this.setState({search: query})
    }
    checkFilterErrors() {
        const game_types = ['show_cash_tables', 'show_tournaments']
        const game_variants = ['show_plo', 'show_nlhe', 'show_bnty']
        const errors = []

        const any_type_checked = game_types.some(
            type => this.state[type]
        )
        if (!any_type_checked) {
            errors.push("* You have to select at least one game type")
        }

        const any_variant_checked = game_variants.some(
            variant => this.state[variant]
        )
        if (!any_variant_checked) {
            errors.push("* You have to select at least one game variant")
        }

        this.setState({filter_errors: errors})
    }
    onToggleCheckbox(checkbox) {
        this.setState(
            { [checkbox]: !this.state[checkbox]},
            this.checkFilterErrors
        )
    }
    onSearch(query) {
        global.location = `${global.location.pathname}?search=${encodeURIComponent(query)}`
    }
    onReload() {
        window.location.reload()
    }
    render() {
        const {errors} = this.props
        const tables = this.filterTables()
        const {search} = this.state

        return <div className="table-grid">
            <style>{style}</style>

            <Row>
                {/*<Col lg={12}>
                    <h1>Tables</h1>
                </Col>*/}
                <Col className="table-options" lg={12}>
                    <div className="tables-actions">
                        <SearchField onSearch={::this.onSearch}
                                    onChange={::this.onFilter}
                                    value={search}
                                    width={300}
                                    placeholder="Search for a table..."/>
                        <a id="new-table-link"
                           className="btn btn-default"
                           href="#new-table-container"
                           onClick={() => !global.user ? this.onNewTable() : {}}>
                            <Icon name="plus"/> Create New
                        </a>
                    </div>
                    <div className="tables-filters">
                        <br/>
                        <input id="cash-t-input"
                               type="checkbox"
                               onChange={() => this.onToggleCheckbox('show_cash_tables')}
                               checked={this.state.show_cash_tables}/>
                        <label className="label-filter" htmlFor="cash-t-input">Cash Tables</label> &nbsp; &nbsp;

                        <input id="cash-to-input"
                               type="checkbox"
                               onChange={() => this.onToggleCheckbox('show_tournaments')}
                               checked={this.state.show_tournaments}/>
                        <label className="label-filter" htmlFor="cash-to-input">Tournaments</label> &nbsp; &nbsp; &nbsp; &nbsp;

                        <input id="omaha-input"
                               type="checkbox"
                               onChange={() => this.onToggleCheckbox('show_plo')}
                               checked={this.state.show_plo}/>
                        <label className="label-filter" htmlFor="omaha-input">Omaha</label> &nbsp; &nbsp;

                        <input id="nlhe-input"
                               type="checkbox"
                               onChange={() => this.onToggleCheckbox('show_nlhe')}
                               checked={this.state.show_nlhe}/>
                        <label className="label-filter" htmlFor="nlhe-input">Hold'Em</label> &nbsp; &nbsp;

                        <input id="bnty-input"
                               type="checkbox"
                               onChange={() => this.onToggleCheckbox('show_bnty')}
                               checked={this.state.show_bnty}/>
                        <label className="label-filter" htmlFor="bnty-input">2/7 Bounty</label>

                        {global.user ? 
                            <span>
                                &nbsp; &nbsp; &nbsp; &nbsp;
                                <input id="locked-input"
                                       type="checkbox"
                                       onChange={() => this.onToggleCheckbox('show_locked')}
                                       checked={this.state.show_locked}/>
                                <label className="label-filter" htmlFor="locked-input">All Levels</label>
                            </span>
                          : null}

                        <br/><br/>
                        <a id='ml-ref'
                           href='#'
                           className="clbl"
                           onClick={() => this.onReload()}>
                            <i className='fa fa-refresh'
                               {...tooltip(`updated: ${this.state.updated} ago`)}></i>
                        </a> &nbsp;
                        {tables.length} active game{tables.length == 1 ? '' : 's'}
                    </div>
                </Col>
                {(errors && errors.length) ?
                    <Alert bsStyle="danger" className="tables-alert">
                        <h4>{errors.join('\n')}</h4>
                    </Alert> : null}
            </Row>

            <br/>

            <Row>
                {!this.state.show_locked ? 
                    <h4 style={{opacity: 0.5}}>
                        Showing only level {this.props.games_level_number} games.<br/><br/>
                        Unlock higher levels by earning more chips at these tables.<br/><br/>
                    </h4>
                  : null}

                {tables.map(table =>
                    table.is_tournament ?
                        <TournamentThumbnail tournament={table} key={table.id}/>
                      : <TableThumbnail table={table} key={table.id}/>
                )}
                {tables.length == 0 &&
                    <h4 style={{opacity: 0.5}}>
                        No games found with the current criteria.
                        <br/>
                        <br/>
                        {this.state.filter_errors.map(error =>
                            <b key={error}>{error}<br/></b>
                        )}
                    </h4>
                }
                <br/>
                {global.user ?
                    <Col sm={2}
                         id="new-table-container"
                         className="table-thumbnail new-table"
                         style={{height: this.state.errors.length ? 'auto' : ''}}>

                        <h4 style={{color: 'black'}}>
                            Create New Game
                        </h4>
                        <hr/>
                        <Tabs bsStyle="pills" defaultActiveKey={1} style={{textAlign: 'center'}} id="type-of-game">
                            <Tab eventKey={1} title="Cash Game" className="cash-game-tab">
                                <TableForm onNewTable={::this.onNewTable}
                                           cashGameBBs={this.props.cash_game_bbs}
                                           thresholdBBEmailVerified={this.props.threshold_bb_email_verified}
                                           state={this.state}/>
                            </Tab>
                            <Tab eventKey={2} title="Tournament" className="tournament-tab">
                                <TournamentForm onNewTable={::this.onNewTable}
                                                tourneyBuyinAmts={this.props.tourney_buyin_amts}
                                                state={this.state}/>
                            </Tab>
                        </Tabs>
                        <small><br/>(All games use play-chips only, no real money)</small>
                    </Col> : null }
            </Row>
            <br/>
            <br/>
        </div>
    }
}


ReactDOM.render(
    React.createElement(TableList, global.props),
    global.react_mount,
)
