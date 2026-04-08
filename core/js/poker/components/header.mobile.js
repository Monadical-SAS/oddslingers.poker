import React from 'react'
import {reduxify} from '@/util/reduxify'

import { DropdownButton, Dropdown } from 'react-bootstrap'

import {Icon} from '@/components/icons'

import {pauseBackend, nextAction} from '@/poker/debugging'
import {
    mapDispatchToProps,
    mapStateToProps,
    ToggleSoundsClass
} from '@/poker/components/header'
import {
    TableInfoModalTrigger,
    ShareTableModalTrigger,
    ReportBugModalTrigger,
    HandHistoryModalTrigger,
    OneTimeBuyModalTrigger,
    AutoRebuyModalTrigger,
    PlayerWinningsModalTrigger
} from '@/poker/components/modals'


class ToggleSounds extends ToggleSoundsClass {
    render() {
        return <Dropdown.Item key="toggle-sounds"
                         onClick={() => this.onToggle() }>
            <Icon name={`volume-${this.state.muted ? 'off' : 'up'}`}/>&nbsp;
            {`${this.state.muted ? 'Unmute' : 'Mute'}`} sounds
        </Dropdown.Item>
    }
}


export const GameHeader = reduxify({
    mapStateToProps,
    mapDispatchToProps,
    render: (props) => {
        return <header className="game-header">
            <DropdownButton bsStyle='default'
                            id="header-settings"
                            title="Options">

                <Dropdown.Item key="game-info">
                    <TableInfoModalTrigger table={props}>
                            <Icon name='bar-chart'/>
                            Game Info
                    </TableInfoModalTrigger>
                </Dropdown.Item>

                {props.is_private &&
                    <Dropdown.Item key="show-player-winnings">
                        <PlayerWinningsModalTrigger>
                            <Icon name='money' /> Show Player Winnings
                        </PlayerWinningsModalTrigger>
                    </Dropdown.Item>}

                <Dropdown.Item key="show-hand-history">
                    <HandHistoryModalTrigger>
                            <Icon name='file-text-o'/> Show Hand History
                    </HandHistoryModalTrigger>
                </Dropdown.Item>

                <Dropdown.Item key="share-table-link">
                    <ShareTableModalTrigger table={props}>
                            <Icon name='share-square'/> Share Table Link
                    </ShareTableModalTrigger>
                </Dropdown.Item>

                <Dropdown.Item key="report-bug">
                    <ReportBugModalTrigger>
                            <Icon name='bug'/> Report a Bug
                    </ReportBugModalTrigger>
                </Dropdown.Item>
                <ToggleSounds muted_sounds={props.muted_sounds}
                              onToggleSound={props.onToggleSound}/>

                {global.props.DEBUG &&
                    <Dropdown.Item key="pause"
                              onClick={pauseBackend}>
                        <Icon name="pause"/> Pause action
                    </Dropdown.Item>
                    }
                {global.props.DEBUG &&
                    <Dropdown.Item key="nextaction"
                              onClick={nextAction}>
                        <Icon name="angle-double-right"/> Next action
                    </Dropdown.Item>
                    }
            </DropdownButton>
        </header>
    }
})

const RebuyMenu = ({bb, can_buy, can_set_auto_rebuy, title,
                    min_buyin, max_buyin, player_auto_rebuy,
                    onSubmitAction}) =>

    <DropdownButton id="rebuy-menu" title={title}>
        {can_buy &&
            <OneTimeBuyModalTrigger min_buyin={min_buyin}
                                    max_buyin={max_buyin}
                                    player_auto_rebuy={player_auto_rebuy}
                                    onSubmitAction={onSubmitAction}>
                <Dropdown.Item className="dropdown-item"
                          key="one-time-buy">
                    Add chips
                </Dropdown.Item>
            </OneTimeBuyModalTrigger>}

        {can_set_auto_rebuy &&
            <AutoRebuyModalTrigger min_buyin={min_buyin}
                                   max_buyin={max_buyin}
                                   bb={bb}
                                   player_auto_rebuy={player_auto_rebuy}
                                   onSubmitAction={onSubmitAction}>
                <Dropdown.Item className="dropdown-item"
                          key="auto-rebuy">
                    Set auto rebuy...
                </Dropdown.Item>
            </AutoRebuyModalTrigger>}
    </DropdownButton>


export const AddChipsButton = reduxify({
    mapStateToProps,
    mapDispatchToProps,
    render: (props) => {
        return !props.is_tournament && props.rebuy ?
            <RebuyMenu onSubmitAction={props.onSubmitAction}
                       title="Chips"
                       {...props.rebuy}/>
            : null
    }
})