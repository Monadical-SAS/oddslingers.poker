import React from 'react'
import {reduxify} from '@/util/reduxify'
import classNames from 'classnames'
import parse from 'date-fns/parse'
import addSeconds from 'date-fns/add_seconds'
import differenceInMilliseconds from 'date-fns/difference_in_milliseconds'

import {playSound} from '@/sounds/reducers'

global.parse = parse


const getColor = (percent) => {
    if (percent > 40) return 'green'

    // interpolate red & green together to create range of colors green -> yellow -> orange -> red
    const frac = (100 - percent) / 100
    let [r,g,b] = [2 * frac, 2 * (1 - frac), 0]
    if (r > 1) r = 1
    if (g > 1) g = 1
    if (b > 1) b = 1
    r = (r*255).toFixed(0)
    g = (g*255).toFixed(0)
    b = (b*255).toFixed(0)
    return `rgba(${r}, ${g}, ${b}, 0.8)`
}

class AutoTimedProgressBarComponent extends React.Component {
    constructor(props) {
        super(props)
        const total_seconds = props.total_seconds
        const start = parse(props.start_time)
        const end = props.end_time ? parse(props.end_time) : addSeconds(start, total_seconds)
        this.state = {
            start,
            end,
            total_seconds,
            progress: 100,
            already_played_sound: false
        }
    }
    preventOutOfRange(percent) {
        if (percent < 3) return 3  // always show a little sliver of red so that the progress bar is visible
        if (percent > 100) return 100
        return percent
    }
    updateProgress() {
        if (global.page.time.speed == 0) return  // pause if animation is paused
        const now = parse(global.page.time.getActualTime())
        const seconds_remaining = differenceInMilliseconds(this.state.end, now)
        const percent = (seconds_remaining)/(this.state.total_seconds * 10)
        if (percent < 0) {
            this.onOutOfTime(seconds_remaining)
            if (this.state.timebank)
                clearInterval(this.timerID)
            else
                this.setTimeBank()
        }

        this.playLowTimeSound(percent)

        this.setState({
            ...this.state,
            seconds_remaining,
            progress: this.preventOutOfRange(percent)
        })
    }
    playLowTimeSound(percent) {
        const is_less_than_15_percent = Math.floor(percent) <= 15
        const is_current_user_acting = this.props.is_current_user_acting
        const not_already_played_sound = !this.state.already_played_sound
        if (is_less_than_15_percent && is_current_user_acting && not_already_played_sound) {
            this.props.playSound('out_of_time')
            this.setState({
                already_played_sound: true
            })
        }
    }
    componentDidMount() {
        this.timerID = setInterval(::this.updateProgress, 100)
    }
    componentWillUnmount() {
        clearInterval(this.timerID)
    }
    setTimeBank() {
        const end = addSeconds(this.state.end, this.props.total_timebank)

        this.setState({
            ...this.state,
            end,
            progress: 100,
            timebank: true,
        })
    }
    onOutOfTime() {
        if (this.props.onOutOfTime)
            this.props.onOutOfTime()
    }
    render() {
        const {color, style, children, show_text, total_timebank} = this.props
        const {progress, seconds_remaining, timebank, total_seconds} = this.state

        return TimedProgressBar({color, style, timebank, children, show_text, total_timebank,
                                 total_seconds, progress, seconds_remaining})
    }
}

export const AutoTimedProgressBar = reduxify({
    mapDispatchToProps: {
        playSound
    },
    render: (props) => {
        return <AutoTimedProgressBarComponent {...props}/>
    }
})


export const TimedProgressBar = ({color, style, timebank, children, show_text, total_timebank,
                                  progress, total_seconds, seconds_remaining}) => {
    progress = progress === undefined ? (seconds_remaining / total_seconds) * 100 : progress
    const bar_style = {
        backgroundColor: color || getColor(progress),
        width: progress + '%',
    }

    const timebank_bar_style = {
        backgroundColor: total_timebank > 5 ? '#337ab7' : '#e7442a',
    }

    let time_name = timebank ? "Timebank" : "Time"
    let content
    if (!children && show_text && (seconds_remaining !== undefined)) {
        content = `${time_name} Remaining: ${seconds_remaining < 0 ? '0'
                  : (seconds_remaining/1000).toFixed(0)} sec`
    } else {
        content = children
    }

    return <div className='timer-container'>
            <div className={classNames('progressbar-container',
                                       {'blink': timebank || (progress < 30)})}
                 style={style || {}}>
                <div className="progressbar-text">{content}</div>
                <div className={classNames('progressbar-progress',
                                           {'progress-bar-stripper progress-bar-danger': timebank})}
                     style={bar_style}></div>
            </div>
        {!timebank && (seconds_remaining < 1500) ?
            <div className={'progressbar-container timebank-container fadeInUp'}
                 style={style || {}}>
                <div className="progressbar-text text-left">Timebank {total_timebank} sec</div>
                <div className="progressbar-progress" style={timebank_bar_style}></div>
            </div>
            : null}
        </div>
}
