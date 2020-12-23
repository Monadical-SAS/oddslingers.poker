/* global d3 */



const draw_axes = ({svg, plot_attrs, render_dims}) => {
    const {scale} = render_dims
    const {x, y} = plot_attrs
    const vw = scale.vw
    const center_x = (render_dims.right - render_dims.left) / 2 + render_dims.left
    const center_y = (render_dims.bottom - render_dims.top) / 2 + render_dims.top
    // axis labels
    svg.append('text')
       .attrs({
           x: vw(45),
           y: center_y,
           transform: `rotate(-90, ${vw(45)}, ${center_y})`,
           class: 'axis-label',
        }).text(y.axis.label)
    svg.append('text')
       .attrs({
           x: center_x,
           y: render_dims.bottom + vw(50),
           class: 'axis-label',
        }).text(x.axis.label)

    // axis ticks
    const tick_attrs = (axis_name, other_dims, type, scale) => {
        const a = axis_name == 'x' ? 'x' : 'y'
        const b = axis_name == 'x' ? 'y' : 'x'
        const b2 = type == 'lg'
            ? scale[b](other_dims.max)
            : scale[b](other_dims.min + other_dims.step_sm)
        return {
            [`${a}1`]: (d) => scale[a](d),
            [`${b}1`]: scale[b](other_dims.min),
            [`${a}2`]: (d) => scale[a](d),
            [`${b}2`]: b2,
            class: 'axis-line',
        }
    }
    const draw_ticks = (ticks_root, axis_name, type, scale, with_labels) => {
        const axis_dims = plot_attrs[axis_name].axis
        const other_name = axis_name == 'x' ? 'y' : 'x'
        const other_dims = plot_attrs[other_name].axis

        const away = (axis_name, n) => axis_name == 'x' ? n * -1 : n

        const ticks = d3.range(
            axis_dims.min,
            axis_dims.max,
            axis_dims[`step_${type}`]
        )
        ticks_root.selectAll(`.${axis_name}-tick-${type}`)
            .data(ticks)
            .enter()
            .append('line')
            .attrs(tick_attrs(axis_name, other_dims, type, scale))

        // axis tick labels
        if (with_labels) {
            const bottom_or_right = scale[other_name](other_dims.min) + away(other_name, vw(20))
            const vertical_align_hack = axis_name == 'y' ? vw(5) : 0
            ticks_root.selectAll(`.${axis_name}-label`)
                .data(ticks.slice(1))
                .enter()
                .append('text')
                .attrs({
                    [axis_name]: (d) => scale[axis_name](d) + vertical_align_hack,
                    [other_name]: bottom_or_right,
                    class: 'axis-tick-label',
                }).text(with_labels)
        }
    }
    let ticks_root = svg.append('g').attr('id', 'tick-wrapper')
    draw_ticks(ticks_root, 'x', 'lg', scale, x.axis.fmt)
    draw_ticks(ticks_root, 'y', 'lg', scale, y.axis.fmt)
    if (x.show_small) {
        draw_ticks(ticks_root, 'x', 'sm', scale, false)
    }
    if (y.show_small) {
        draw_ticks(ticks_root, 'y', 'sm', scale, false)
    }
}

const draw_plot_skeleton = ({svg, plot_attrs, render_dims}) => {
    const center_x = (render_dims.right - render_dims.left) / 2 + render_dims.left
    svg.append('rect').attrs({
        rx: 15,
        ry: 15,
        height: "100%",
        width: "100%",
        class: 'background'
    })
    svg.append('text').attrs({
        x: center_x,
        y: render_dims.top - render_dims.scale.vw(25),
        class: 'plot-title',
    }).text(plot_attrs.title)

    svg.append('rect').attrs({
        x: render_dims.left,
        y: render_dims.top,
        width: render_dims.right - render_dims.left,
        height: render_dims.bottom - render_dims.top,
        class: 'plot-background',
    })

    draw_axes({svg, plot_attrs, render_dims})
}

const draw_legend = ({svg_root, data, render_dims, legend_attrs}) => {
    const vw = render_dims.scale.vw

    svg_root.append('rect').attrs({...legend_attrs, fmt: null})
    const legend = svg_root.append('g').attr('id', 'legend-wrapper')

    const legend_data = data.map((d, idx) => {
        return {
            fill: d.color,
            x: legend_attrs.x + vw(20) + Math.floor(idx / 2) * (legend_attrs.width - vw(70)) / 2,
            y: legend_attrs.y + vw(20) + (idx % 2) * vw(50),
            label: d.label,
            value: d.x * d.y,
        }
    })

    legend.selectAll('.legend-sq')
          .data(legend_data)
          .enter()
          .append('rect')
          .attrs((d) => {
              return {
                  ...d,
                  height: vw(30),
                  width: vw(30),
              }
          })
    legend.selectAll('.legend-text')
          .data(legend_data)
          .enter()
          .append('text')
          .attrs((d, i) => {
              return {
                  x: d.x + vw(40),
                  y: d.y + vw(20),
                  class: 'legend-text',
                  id: `label-${i}`,
              }
          }).text(legend_attrs.fmt)
}
const create_table_of_contents = (div_id) => {
    const header = /[hH][12345]$/
    const process_node = (node, headers) => {
        // console.log('processing', node.tagName, headers.id)
        if (header.test(node.tagName)) {
            const new_id = (node.textContent || node.innerText).replace(/ /g, '-')
            node.setAttribute('id', new_id)

            headers.push(node)
            node.childNodes.forEach((node) => process_node(node, headers))
        }
    }
    const headers = []
    document.body.childNodes.forEach((node) => process_node(node, headers))

    const contents_root = document.getElementById(div_id)
    const contents_header = document.createElement('h1')
    contents_header.appendChild(document.createTextNode('Contents'))
    contents_root.appendChild(contents_header)
    const createListItem = (node) => {
        const li = document.createElement('li')
        const link = document.createElement('a')
        link.setAttribute('href', `#${node.id}`)
        const text = document.createTextNode(node.textContent || node.innerText)
        link.appendChild(text)
        li.appendChild(link)
        li.level = node.tagName[1]
        return li
    }
    headers.reduce((prev, node) => {
        // console.log('REDUCING:', {prev: prev.level, node: node.tagName})
        // if (node.tagName == 'H4') {debugger}
        let ul
        if (prev.id == div_id || Number(node.tagName[1]) > Number(prev.level)) {
            // console.log('\tdown')
            ul = document.createElement('ul')
            prev.appendChild(ul)
            // console.log('\tappended', ul, 'to', prev)
        } else {
            while (Number(node.tagName[1]) < Number(prev.level)) {
                // console.log('\tup')
                prev = prev.parentNode
            }
            // console.log('\tselected', prev)
            ul = prev.parentNode
        }
        const li = createListItem(node)
        ul.appendChild(li)
        // console.log('\tappended', li, 'to', ul)
        return li
    }, contents_root)
}

const get_triangle = (p) => [
    {x: 0, y: 0},
    {x: p.x, y: 0},
    {x: 0, y: p.y},
]

const scaled_points_str = (points, scale) => {
    return points.map((p) => `${scale.x(p.x)},${scale.y(p.y)}`).join(' ')
}

const draw_polygons = ({svg_root, data, render_dims}) => {
    svg_root.selectAll('.auc')
       .data(data)
       .enter()
       .append("polygon")
       .attrs({
           id: (d, i) => `polygon-${i}`,
           class: 'auc',
           points: (d) => scaled_points_str(get_triangle(d), render_dims.scale),
           fill: (d) => d.color,
           'fill-opacity': '0.7',
       })
}

const update_and_redraw = ({svg, circle, plot_attrs, legend_attrs, render_dims, os_data, os_idx}) => {
    const [e_x, e_y] = d3.mouse(svg.node())
    // console.log(svg)
    // raw = [circle.attr('cy'), e_y]
    // console.log('raw', raw)
    // inverted = raw.map(render_dims.scale.y.invert)
    // console.log('inverted', inverted)
    // scaled = inverted.map(render_dims.scale.y)
    // console.log('scaled(inverted)', scaled)

    if (render_dims.scale.x.invert(circle.attr('cx')) == 0) {
        const new_y = render_dims.scale.y.invert(e_y)
        if (new_y < 15 || new_y > plot_attrs.y.axis.max) {
            return
        }
        os_data.y = new_y
        circle.attr('cy', render_dims.scale.y(new_y))
    } else {
        const new_x = render_dims.scale.x.invert(e_x)
        if (new_x < 80 || new_x > plot_attrs.x.axis.max) {
            return
        }
        os_data.x = new_x
        circle.attr('cx', render_dims.scale.x(new_x))
    }
    d3.select(`#label-${os_idx}`)
                    .text(legend_attrs.fmt({
                        value: os_data.x * os_data.y,
                        label: os_data.label,
                    }))

    const polygon = d3.select(`#polygon-${os_idx}`)
    polygon.attr('points', scaled_points_str(get_triangle(os_data), render_dims.scale))
}

const monetization_plot = (svg_id) => {
    const svg = d3.select(`#${svg_id}`)
    svg.attr('width', '100%')
    svg.attr('width', svg.node().getBoundingClientRect().width)
    svg.attr('height', svg.node().getBoundingClientRect().width * 0.7)
    const data = [
        {
            label: 'poker',
            x: 80, y: 50,
            color: '#fe111b',
        },
        {
            label: 'eSports 2020 (est.)',
            x: 286, y: 5.2,
            color: '#05ccea'
        },
        {
            label: 'eSports',
            x: 191, y: 3.6,
            color: '#edae49'
        },
        {
            label: 'OddSlingers Poker (potential)',
            x: 160, y: 45,
            color: '#3dbb00',
        },
    ]
    const os_idx = 3

    const plot_attrs = {
        title: 'Monetization',
        x: {
            axis: {
                fmt: (d) => d,
                min: 0,
                max: 350,
                step_sm: 10,
                step_lg: 50,
                show_small: false,
                label: 'Number of individuals (millions)',
            },
        },
        y: {
            axis: {
                fmt: (d) => `$${d}`,
                min: 0,
                max: 60,
                step_sm: 2,
                step_lg: 10,
                show_small: false,
                label: 'Revenue/individual (dollars per yr)',
            },
        },
    }

    const vw = (n) => svg.attr('width') / 1000 * n

    const _render_dims = {
        top: vw(100),
        left: vw(100),
        bottom: svg.attr('height') - vw(250),
        right: svg.attr('width') - vw(100),
    }
    const render_dims = {
        ..._render_dims,
        scale: {
            x: d3.scaleLinear()
                 .domain([plot_attrs.x.axis.min, plot_attrs.x.axis.max])
                 .range([_render_dims.left, _render_dims.right]),

            y: d3.scaleLinear()
                 .domain([plot_attrs.y.axis.min, plot_attrs.y.axis.max])
                 .range([_render_dims.bottom, _render_dims.top]),
            vw: vw,
        },
    }

    const legend_attrs = {
           x: render_dims.left,
           y: render_dims.bottom + vw(80),
           height: vw(120),
           width: render_dims.right - render_dims.left,
           class: 'legend',
           fmt: ({value, label}) => `$${(value/1000).toFixed(1)}Bn/yr: ${label}`,
    }

    draw_plot_skeleton({svg, plot_attrs, legend_attrs, render_dims})

    const svg_root = svg.append('g').attr('id', 'data-root')
    draw_legend({svg_root, data, plot_attrs, render_dims, legend_attrs})
    draw_polygons({svg_root, data, plot_attrs, render_dims, legend_attrs})

    const circle_pts = [
        {
            x: 0,
            y: data[os_idx].y,
        },
        {
            x: data[os_idx].x,
            y: 0,
        },
    ]

    function drag() {
        update_and_redraw({
            circle: d3.select(this),
            event: d3.event,
            os_data: data[os_idx],
            plot_attrs,
            render_dims,
            os_idx,
            legend_attrs,
            svg,
        })
    }

    const circles = svg_root.selectAll('.control')
                            .data(circle_pts)
    circles.enter()
           .append('circle')
           .attrs({
               cx: (d) => render_dims.scale.x(d.x),
               cy: (d) => render_dims.scale.y(d.y),
               r: vw(6),
               class: 'controls',
           })
           .call(d3.drag()
                   .on("start", drag)
                   .on("drag", drag)
                   .on("end", drag))
}
const tokensale_plot = (svg_id) => {
    const svg = d3.select(`#${svg_id}`)
    svg.attr('width', '100%')
    svg.attr('width', svg.node().getBoundingClientRect().width)
    svg.attr('height', svg.node().getBoundingClientRect().width * 0.7)


    const plot_attrs = {
        title: 'Token Distribution',
        x: {
            axis: {
                fmt: (d) => `${d}:00`,
                min: 0,
                max: 500,
                step_sm: 10,
                step_lg: 50,
                show_small: false,
                label: 'Hours passed',
            },
        },
        y: {
            axis: {
                fmt: (d) => `${d}%`,
                min: 0,
                max: 100,
                step_sm: 2,
                step_lg: 10,
                show_small: false,
                label: '% Owned',
            },
        },
    }

    const vw = (n) => svg.attr('width') / 1000 * n

    const _render_dims = {
        top: vw(100),
        left: vw(100),
        bottom: svg.attr('height') - vw(250),
        right: svg.attr('width') - vw(100),
    }
    const render_dims = {
        ..._render_dims,
        scale: {
            x: d3.scaleLinear()
                 .domain([plot_attrs.x.axis.min, plot_attrs.x.axis.max])
                 .range([_render_dims.left, _render_dims.right]),

            y: d3.scaleLinear()
                 .domain([plot_attrs.y.axis.min, plot_attrs.y.axis.max])
                 .range([_render_dims.bottom, _render_dims.top]),
            vw: vw,
        },
    }


    const buyer_share = (x) => 0.1 + Math.sqrt(x) / (Math.sqrt(500) * 2)
    // const other_share = (x) => (1 - buyer_share(x)) / 2 + buyer_share(x)

    const data = [
        // {
        //     label: 'Platform',
        //     color: 'darkolivegreen',
        // },
        {
            func: () => 1,
            // func: other_share,
            label: 'Founder, advisors, and early investors',
            color: 'darkolivegreen',
        },
        {
            func: buyer_share,
            label: 'Token sale purchasers',
            color: 'steelblue',
        },
    ]
    const legend_attrs = {
           x: render_dims.left,
           y: render_dims.bottom + vw(80),
           height: vw(120),
           width: render_dims.right - render_dims.left,
           class: 'legend',
           fmt: ({label}) => label
    }

    draw_plot_skeleton({
        svg: svg.append('g').attr('id', 'plot-skeleton'),
        plot_attrs, render_dims
    })
    draw_legend({
        svg_root: svg,
        data, plot_attrs, render_dims, legend_attrs,
    })
    const step = 1
    const xs = d3.range(plot_attrs.x.axis.min, plot_attrs.x.axis.max + step, step)

    const get_area = (func) => d3.area()
                                 .curve(d3.curveMonotoneX)
                                 .x((d) => render_dims.scale.x(d))
                                 .y0(() => render_dims.scale.y(0))
                                 .y1((d) => render_dims.scale.y(func(d) * 100))

    const curve_container = svg.append('g').attr('id', 'curve-container')

    data.forEach((dat) =>
        curve_container.append('path')
                       .datum(xs)
                       .attrs({
                            class: 'area',
                            d: get_area(dat.func),
                            fill: dat.color,
                            'fill-opacity': '0.9',
                        })
    )
}

window.init = () => {
    monetization_plot('monetization-plot')
    tokensale_plot('tokensale-plot')
    create_table_of_contents('table-of-contents')
}
