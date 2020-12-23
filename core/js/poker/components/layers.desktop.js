import React from 'react'
import {reduxify} from '@/util/reduxify'
import classNames from 'classnames'

import {getUrlParams, isEmbedded} from '@/util/browser'

import {TableBotProfile} from '@/components/bot-profile'
import {GameHeader, TableOptionsButton, AddChipsButton} from '@/poker/components/header.desktop'
import {Board, DealerButton} from '@/poker/components/board.desktop'
import {Pot} from '@/poker/components/pot.desktop'
import {Seat} from '@/poker/components/seat.desktop'
import {SeatCards} from '@/poker/components/cards.desktop'
import {SeatChips} from '@/poker/components/chips.desktop'
import {PassiveActions} from '@/poker/components/passive-actions.desktop'
import {Chat} from '@/chat/components.desktop'
import {ChatBubbles} from '@/chat/bubbles.desktop'
import {LeaveToPage} from '@/poker/components/passive-actions'

import {
    mapStateToProps,
    ForEachPosition,
    BackgroundLayer,
    FeltLayer,
    ActionsLayer,
    PreActionsLayer,
    confirmClose,
    tournamentHasFinished
} from '@/poker/components/layers'


export const HeaderLayer = () =>
    <div className="table-layer layer-header">
        <GameHeader/>
    </div>

export const TableOptionsLayer = () =>
    <div className="table-layer layer-table-options">
        <TableOptionsButton/>
        <AddChipsButton/>
    </div>

export const BoardLayer = () =>
    <div className="table-layer layer-board">
        <Board/>
    </div>

export const PassiveActionsLayer = () =>
    <div className="table-layer layer-passive-actions">
        <PassiveActions/>
    </div>

export const PotLayer = () =>
    <div className="table-layer layer-pot">
        <Pot/>
    </div>

export const SeatsLayer = () =>
    <ForEachPosition component={Seat} className="table-layer layer-seats"/>

export const CardsLayer = () =>
    <ForEachPosition component={SeatCards} className="table-layer layer-cards"/>

export const ChipsLayer = () =>
    <ForEachPosition component={SeatChips} className="table-layer layer-chips"/>

export const BubblesLayer = () =>
    <ForEachPosition component={ChatBubbles} className="table-layer layer-bubbles"/>

export const LeaveSeatLayer = () =>
    <div className="table-layer layer-leave-seat">
        <LeaveToPage/>
    </div>

export const BotProfileLayer = () =>
    <ForEachPosition component={TableBotProfile} className="table-layer layer-bot-profile"/>

class TablePanelComponent extends React.Component {
    componentWillReceiveProps(nextProps) {
        if (nextProps.logged_in_player && !isEmbedded()) {
            global.onbeforeunload = (e) => confirmClose(e)
        }
    }
    render() {
        const {className, gameVariantClass, logged_in_player, tournament} = this.props
        let layers = [
            <BackgroundLayer key="bg"/>,
            <FeltLayer key="felt"/>,
            <HeaderLayer key="header"/>,
            <TableOptionsLayer key="table-options"/>,
            <BoardLayer key="board"/>,
            <PotLayer key="pot"/>,
            <CardsLayer key="cards"/>,
            <ChipsLayer key="chips"/>,
            <BubblesLayer key="bubbles"/>,
            <BotProfileLayer key='bot-profiles'/>,
        ]
        if (!tournamentHasFinished(tournament)) {
            layers = [
                ...layers,
                <SeatsLayer key="seats"/>,
                <DealerButton key="dealer"/>,
            ]
        }
        if (logged_in_player && !tournamentHasFinished(tournament)) {
            layers = [
                ...layers,
                <ActionsLayer key="actions"/>,
                <PreActionsLayer key="pre-actions"/>,
                <PassiveActionsLayer key="passive-actions"/>,
            ]
        }

        return <div className="layers-container">
            <div className={classNames('table', 'table-layers', className, gameVariantClass)}>
                {layers || ''}
            </div>
            <LeaveSeatLayer/>
            {getUrlParams(window.location.search).nochat ?
                null
              : <Chat/>}
        </div>
    }
}

export const TablePanel = reduxify({
    mapStateToProps,
    render: (props) =>
        <TablePanelComponent {...props}/>
})
