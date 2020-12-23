import {reduxify} from '@/util/reduxify'

import {getGamestate} from "@/poker/selectors"
import {calculateTableCSS} from "@/poker/css.mobile"

import {PotContainer} from '@/poker/components/pot'


const getChipStyle = (curr_idx) => ({
    bottom: curr_idx * 2
})

export const Pot = reduxify({
    mapStateToProps: (state) => {
        const {table, players} = getGamestate(state)
        const sidepot_summary = table.sidepot_summary
        const css = calculateTableCSS({table, players})
        const style = css.table.sidepot_summary.style
        const show_detailed_chips = false
        return {sidepot_summary, style, getChipStyle, show_detailed_chips}
    },
    ...PotContainer
})
