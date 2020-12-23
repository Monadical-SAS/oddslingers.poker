import React from 'react'

import {PotChips} from '@/poker/components/chips'


export const PotContainer = {
    render(props) {
        return <div className="pots" style={props.style ? {...props.style} : {}}>
            {Object.keys(props.sidepot_summary)
                .filter(pot_id =>
                    pot_id != 'style'
                    && props.sidepot_summary[pot_id]
                    && props.sidepot_summary[pot_id].amt
                ).map(pot_id =>
                    <PotChips
                        key={pot_id}
                        show_detailed_chips={props.show_detailed_chips && true}
                        number={Number(props.sidepot_summary[pot_id].amt)}
                        className={`pot-${pot_id}`}
                        style={props.sidepot_summary[pot_id].style || {}}
                        getChipStyle={props.getChipStyle}/>)}
        </div>
    },
}
