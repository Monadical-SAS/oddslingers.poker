import React from 'react'
import ReactDOM from 'react-dom'

import Row from 'react-bootstrap/lib/Row'
import Col from 'react-bootstrap/lib/Col'
import Alert from 'react-bootstrap/lib/Alert'
import Tabs from 'react-bootstrap/lib/Tabs'
import Tab from 'react-bootstrap/lib/Tab'

import {SearchField} from '@/components/search-field'
import {Spinner} from '@/components/icons'
import {chipAmtStr} from '@/util/javascript'
import {getSearchHashInUrl} from '@/util/browser'

const chipColor = (winnings) =>
    Number(winnings) >= 0 ? 'green' : 'red'

const chipsSign = (winnings) =>
    Number(winnings) > 0 ? '+' : ''

const formatNumber = (num) =>
    Number(num).toLocaleString()

const LeaderboardProfile = ({user, className}) =>
    user ? <a href={`/user/${user.username}/`} className={className}>
        <Col sm={2}
             className='leaderboard-thumbnail'>
            <h2>{user.ranking < 10 ? <span>#{user.ranking + 1} &nbsp;</span> : null}
                {user.username.slice(0, 12)}
            </h2>
            <hr className="orange-separator"/>
            <div style={{fontSize: '1.5em', opacity: 0.7}}>
                <b title="Badges">
                    <i style={{color: 'orange'}} className="fa fa-star"></i> {formatNumber(user.badge_count)}
                </b>
                &nbsp; &nbsp; &nbsp;
                {user.winnings ?
                    <b style={{color: chipColor(user.winnings)}}>
                        {`${chipsSign(user.winnings)}${formatNumber(user.winnings)}`} ㆔
                    </b> : null}
            </div>
            <hr className="orange-separator"/><br/>
            <div className="profile-pic-wrapper">
                <span className="vertical-alignment-helper"/>
                <img src={user.profile_image || "/static/images/chip.png"} className="profile-pic"/>
            </div>
            {user.tables ?
                <div>
                    <br/>
                    <span>{user.tables.length ? 'Recently active on:' : 'No active tables.'}</span>
                    <hr/>
                    <Row className="mini-tables">
                        {user.tables.length ?
                            user.tables.map(table =>
                                <a href={table.path} key={table.id}>
                                    {table.name}
                                </a>)
                          : <h4>Offline</h4>
                        }
                    </Row>
                </div> : null}
        </Col>
    </a> : null


class UserList extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            current_top: props.current_top,
            past_top: props.past_top,
            search: getSearchHashInUrl(),
            errors: props.errors,
            loading: false,
            nonce: 0,
        }
    }
    componentDidMount() {
        // display search results if there is a search hash in URL
        if (document.location.hash.indexOf('#filter=') == 0) {
            const query = decodeURIComponent(document.location.hash.split('#filter=', 2)[1])
            // console.log(document.location.hash, query)
            this.onFilter(query)
        }
    }
    onFilter(query) {
        if (!query.length) {
            this.setState({search: '', errors: [], loading: true})
            global.history.pushState({}, document.title, '/leaderboard/');
            $.get(`/leaderboard/?props_json=1`, ({current_top, errors}) => {
                this.setState({current_top, errors, loading: false})
            })
        } else {
            const nonce = this.state.nonce + 1
            this.setState({search: query, loading: true, nonce})
            global.history.pushState({}, document.title, `/leaderboard/?search=${query}`);
            $.get(`/leaderboard/?search=${query}&props_json=1`, ({current_top, errors}) => {
                if (Array.isArray(current_top) && nonce == this.state.nonce) {
                    this.setState({current_top, errors, loading: false})
                }
            })
        }
    }
    onSearch(query) {
        global.location = `${global.location.pathname}?search=${encodeURIComponent(query)}`
    }
    onInvite() {
        const invite_email = $('#new-user-email').val()
        const subject = 'Come play poker with me on Oddslingers!'
        const body = `I invite you to join me for a game of poker on oddslingers.com!\n\
                      \nYou can sign up here: https://oddslingers.com/accounts/signup/\n\
                      \n--From ${global.user.username}`
        global.open(`mailto:${invite_email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`)
    }
    render() {
        const {total_winnings, all_time_winnings, total_users, seasons} = this.props
        const {current_top, search, errors, loading} = this.state

        const user_list = current_top || []

        return <div className="table-grid leaderboard-grid">
            <Row>
                <center>
                    <div className="leaderboard-actions">
                        <Spinner style={{opacity: loading ? 1 : 0}}/>
                        <SearchField onSearch={::this.onSearch}
                                     onChange={::this.onFilter}
                                     value={search}
                                     bsStyle={'default'}
                                     placeholder="Search for a player..."/>

                        {/*&nbsp;&nbsp;
                        <Button><Icon name="plus"/> Invite a Player...</Button>*/}
                    </div>

                    {(errors && errors.length) ?
                        <Alert bsStyle="danger" className="tables-alert">
                            <h4>{errors.join('\n')}</h4>
                        </Alert> : null}
                </center>
            </Row>

            {(search || loading) ?
                <div>
                    <br/><br/>
                    {user_list.map(user =>
                        <LeaderboardProfile user={user} key={user.id}/>)}
                </div>
              : <Tabs defaultActiveKey={1} id="leaderboard-tabs">
                    <hr className="tabs-divider"/>
                    <Tab eventKey={1} title="Top Players This Week">
                        <Row className="leaderboard-top">
                            <LeaderboardProfile user={user_list[1]} className='silver-leader'/>
                            <LeaderboardProfile user={user_list[0]} className='golden-leader'/>
                            <LeaderboardProfile user={user_list[2]} className='bronze-leader'/>
                        </Row>
                        {(total_winnings && !search.length) ?
                            <h3>{chipAmtStr(total_winnings, true)} chips won this week. {chipAmtStr(all_time_winnings, true)} chips in circulation.</h3> : null}
                        <br/>
                        <Row>
                            {user_list.slice(3).map(user =>
                                <LeaderboardProfile user={user} key={user.id}/>)}
                        </Row>
                    </Tab>

                    {/*<Tab eventKey={2} title="Top Players Last Week">
                        <Row className="leaderboard-top">
                            <LeaderboardProfile user={past_top[1]} style={{height: 450, width: 290, borderColor: 'orange', borderWidth: 5}}/>
                            <LeaderboardProfile user={past_top[0]} style={{height: 520, width: 300, borderColor: 'gold', borderWidth: 10}}/>
                            <LeaderboardProfile user={past_top[2]} style={{height: 420, width: 290, borderColor: 'silver', borderWidth: 5}}/>
                        </Row>
                        <br/>
                        <Row>
                            {past_top.slice(3).map(user =>
                                <LeaderboardProfile user={user} key={user.id}/>)}
                        </Row>
                    </Tab>*/}

                    {seasons.map((users, idx) =>
                        <Tab eventKey={idx+3} title={idx ? 'Current Season' : 'Last Season'}>
                            <div>
                                <Row className="leaderboard-top">
                                    <LeaderboardProfile user={users[1]} className='silver-leader'/>
                                    <LeaderboardProfile user={users[0]} className='golden-leader'/>
                                    <LeaderboardProfile user={users[2]} className='bronze-leader'/>
                                </Row>
                                <br/>
                                <Row>
                                    {users.slice(3).map(user =>
                                        <LeaderboardProfile user={user} key={user.id}/>)}
                                </Row>
                            </div>
                        </Tab>
                    )}
                </Tabs>
            }

            <br/><br/>
            {(search && user_list.length == 0) ?
                <Alert bsStyle="warning" className="tables-alert">
                    <br/>
                    <h4>No players found matching "{search}".</h4>
                </Alert> : null}
            <br/>
            <Row>
                <br/>
                <Col md={12} className="footer-stats">
                    <h2>
                        <br/>
                        <span className="nowrap">{user_list.length}/{total_users} Players</span>
                    </h2>
                </Col>
            </Row>
        </div>
    }
}


ReactDOM.render(
    React.createElement(UserList, global.props),
    global.react_mount,
)
