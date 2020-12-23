import {reduxify} from '@/util/reduxify'

import {getGamestate} from "@/poker/selectors"

import {PotContainer} from '@/poker/components/pot'


const getChipStyle = (curr_idx) => ({
    bottom: curr_idx * 5
})

export const Pot = reduxify({
    mapStateToProps: (state) => {
        const {sidepot_summary} = getGamestate(state).table
        const show_detailed_chips = true
        return {sidepot_summary, show_detailed_chips, getChipStyle}
    },
    ...PotContainer
})
