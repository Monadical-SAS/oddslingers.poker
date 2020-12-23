import React from 'react'
import classNames from 'classnames'
import {reduxify} from '@/util/reduxify'

import isEqual from 'lodash/isEqual'

import Alert from 'react-bootstrap/lib/Alert'
import Button from 'react-bootstrap/lib/Button'

import {DealerButtonComponent} from '@/poker/components/board'
import {Cards} from '@/poker/components/cards'

import {tooltip} from '@/util/dom'
import {select_text} from '@/util/browser'
import {Icon, Spinner} from '@/components/icons'

import {getGamestate, getActivePlayers} from "@/poker/selectors"
import {calculateTableCSS} from "@/poker/css.desktop"


class EmptyBoardComponent extends React.PureComponent {
    render() {
        return <div className="board">
            <Alert id="empty-table-message" bsStyle="success">
                <h4>Invite people to begin playing.</h4>

                <pre id="share-link" style={{userSelect: 'all', textAlign: 'center'}}>
                    {this.props.share_url}
                </pre>
                <Button bsStyle="default"
                        onClick={() => (document.execCommand('copy'), true)}
                        {...tooltip("Copy to clipboard", "right")}>
                    <Icon name="clipboard"/>
                </Button>
                <hr/>
                <a className={classNames("twitter-share-button", "btn btn-default")}
                    href={this.props.tweet_url}
                    target="_blank"
                    rel="noopener">
                    <Icon name="twitter"/> &nbsp;Tweet table invite
                </a> &nbsp;
                <a className={classNames("twitter-share-button", "btn btn-discord")}
                    href={this.props.discord_url}
                    target="_blank"
                    rel="noopener">
                    <Icon name="gamepad"/> &nbsp;Challenge a player on Discord
                </a>
                <div style={{marginTop: 8, fontSize: 16}}>
                    Waiting for more players to start game... &nbsp; <Spinner/>
                </div>
            </Alert>
        </div>
    }
}


class BoardComponent extends React.Component {
    shouldComponentUpdate(nextProps) {
        if (nextProps.is_empty_table != this.props.is_empty_table) return true
        if (nextProps.has_pot != this.props.has_pot) return true
        if (nextProps.total_pot_string != this.props.total_pot_string) return true
        if (!isEqual(nextProps.board, this.props.board)) return true
        return false
    }
    render() {
        return <div className="board">
            {(!this.props.is_empty_table && this.props.has_pot) ?
                <div className="total-pot">
                    Total Pot: {this.props.total_pot_string} {this.props.total_pot_string == '1' ? 'chip' : 'chips'}
                </div> : null}
            <Cards cards={this.props.board || []} className="board-cards"/>

            {/*(is_empty_table && global.innerWidth > 1000) ?
                <Snake/> : null*/}
        </div>
    }
}

export const BoardContainer = {
    mapStateToProps: (state) => {
        const {table, players} = getGamestate(state)
        const {board, total_pot, path} = table
        const is_empty_table = getActivePlayers(players).length < 2
        const has_pot = Number(total_pot) > 0
        const total_pot_string = Number(total_pot).toLocaleString()
        const share_url = `${global.location.origin}${path}`

        const tweet_url = "https://twitter.com/intent/tweet?text=" +
            encodeURIComponent(`Join the poker game on @OddSlingers: ${table.name} ${share_url}`)
        const discord_url = "https://discord.gg/Avx4bds"

        const tournament = table.tournament

        return {board, is_empty_table, has_pot, total_pot_string, share_url,
                tweet_url, discord_url, tournament}
    },
    render: (props) => {
        if (props.tournament && props.tournament.status === 'FINISHED') {
            return <div className="board">
                <Alert id="empty-table-message" bsStyle="info">
                    <h4>This tournament has finished</h4>
                    <Button bsStyle="default"
                            onClick={() => global.location = props.tournament.path}>
                        Check the results
                    </Button>
                </Alert>
            </div>
        }
        if (props.is_empty_table) {
            select_text("share-link")
            return <EmptyBoardComponent share_url={props.share_url}
                                        tweet_url={props.tweet_url}
                                        discord_url={props.discord_url}/>
        }
        return <BoardComponent {...props} />
    }
}

export const Board = reduxify(BoardContainer)

export const DealerButton = reduxify({
    mapStateToProps: (state) => {
        const {table, players} = getGamestate(state)
        const css = calculateTableCSS({table, players})

        return {btn_coord: css.table.btn.style}
    },
    render: ({btn_coord}) => {
        return <DealerButtonComponent btn_coord={btn_coord}/>
    }
})
