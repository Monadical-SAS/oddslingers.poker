import {range, mapObj, select} from '@/util/javascript'
import {is_portrait} from '@/util/browser'
import {getLoggedInPlayerId} from '@/poker/selectors'


const ellipse = (height, width, angle, h_offset=0, w_offset=0) => {
    // TODO make this a real ellipse instead of a circle
    return {left: (width + w_offset) * Math.cos(angle),
            top: (height + h_offset) * Math.sin(angle)}
}
const add_pts = (pt1, pt2) => {
    return {left: pt1.left + pt2.left, top: pt1.top + pt2.top}
}
const scale_pt = (pt, scalar) => {
    return {left: pt.left * scalar, top: pt.top * scalar}
}

export const center = ({width, height}, elem) =>
    elem ? ({
        top: height/2 - elem.height/2,
        left: width/2 - elem.width/2,
    }) : ({
        top: height/2,
        left: width/2,
    })

export const ellipse_positions = (n_players, center, radius_scale=1,
                                  h_offset=0, w_offset=0) => {
    const angle_between_plyr = 2 * Math.PI / n_players

    return range(n_players).map(idx => {     // 0, 1, ..., n_players
        let angle
        if (n_players % 2) {
            angle = angle_between_plyr * (idx + 0.5)
        } else {
            angle = angle_between_plyr * idx
        }
        //  player 1 at bottom
        angle = angle_between_plyr * idx + Math.PI / 2
        return add_pts(
            scale_pt(
                ellipse(center.top, center.left, angle, h_offset, w_offset),
                radius_scale
            ),
            center,
        )
    })
}

export const getBtnPosition = (n_players, center, radius_scale, btn_positions,
                               s_offset, w_offset, btn_position) => {
    const n_arcs = n_players * 11
    const positions = ellipse_positions(
        n_arcs, center, radius_scale, s_offset, w_offset
    )
    const idx = btn_positions[n_players][btn_position]
    const out = positions[idx]
    return out
}

export const getPlayerPosition = (plyr_position, players, num_seats) => {
    if ((plyr_position !== null) && (plyr_position !== undefined)){
        plyr_position = Number(plyr_position)
        const current_plyr_id = getLoggedInPlayerId(players)
        const logged_in_plyr_position = current_plyr_id !== null ?
                                        players[current_plyr_id].position
                                        : 0
        const position_dif = plyr_position - logged_in_plyr_position
        return position_dif >= 0 ? position_dif : (num_seats - logged_in_plyr_position) + plyr_position
    }
    return 0
}


export const ellipse_offset = (value) =>
    value + (is_portrait() ? 300 : 0)

export const offset = ({top, left}) => ({top, left})

export const toCenter = ({top, left, width, height}, elem) => {
    const center_obj = center({width, height}, elem)
    return {
        top: top + center_obj.top,
        left: left + center_obj.left,
    }
}

export const centerToOffset = ({top, left}, {width, height}) => ({
    top: top - height/2,
    left: left - width/2,
})

export const offsetToCenter = ({top, left}, {width, height}) => ({
    top: top + height/2,
    left: left + width/2,
})


export const styleFor = (css, path) =>
    select(css, path + '/style')

const addUnits = (obj) =>
    mapObj(obj, (key, val) => {
        if (typeof(val) === 'number')
            return `${val}px`
        else if (typeof(val) === 'object')
            return addUnits(val)
        return val
    })

export const styleForWithUnits = (css, path) =>
    addUnits(styleFor(css, path))

